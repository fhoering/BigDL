#
# Copyright 2016 The BigDL Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# This file is adapted from https://github.com/PyTorchLightning
# /pytorch-lightning/blob/master/pytorch_lightning/plugins/training_type/ddp_spawn.py
#
# Copyright The PyTorch Lightning team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import cloudpickle
import multiprocessing
import os
import subprocess
import sys
from tempfile import TemporaryDirectory

import torch

from bigdl.nano.pytorch.plugins.ddp_spawn import DDPSpawnPlugin

import logging
log = logging.getLogger(__name__)


def queue_dumper(q):
    """
    Copy values from Queue into a List.
    """
    q_list = []
    while not q.empty():
        q_list.append(q.get())
    return q_list


def queue_loader(q_list):
    """
    Copy values from a List into a SimpleQueue.
    """
    q = multiprocessing.SimpleQueue()
    for item in q_list:
        q.put(item)
    return q


class DDPSubprocessPlugin(DDPSpawnPlugin):
    distributed_backend = "ddp_subprocess"

    def _run_subprocess(self, tmpdir):
        from bigdl.nano.common.cpu_schedule import schedule_workers

        cpu_procs = schedule_workers(self.num_processes)

        processes = []
        cwd_path = os.path.split(os.path.realpath(__file__))[0]
        for i in range(self.num_processes):
            env = {
                "KMP_AFFINITY": f"granularity=fine,proclist"
                                f"=[{','.join([str(i) for i in cpu_procs[i]])}],explicit",
                "OMP_NUM_THREADS": str(len(cpu_procs[i])),
                "PROCESS_IDX": str(i),
            }
            if "PYTHONPATH" in os.environ:
                env["PYTHONPATH"] = os.environ["PYTHONPATH"]
            processes.append(subprocess.Popen([sys.executable, f"{cwd_path}/worker.py",
                                               tmpdir], env=env))

        return processes

    def start_training(self, trainer):
        self.model._ortsess = None
        self.execution_loop()
        trainer.optimizers = []

    def start_evaluating(self, trainer):
        print("evaluate")
        self.execution_loop()

    def start_predicting(self, trainer):
        print("predict")
        self.execution_loop()

    def execution_loop(self):
        if self.is_global_zero and not torch.distributed.is_initialized():
            log.info("-" * 100)
            log.info(f"distributed_backend={self.distributed_backend}")
            log.info(f"All DDP processes registered. Starting ddp with {self.world_size} processes")
            log.info("-" * 100)

        with TemporaryDirectory() as temp_dir:
            with open(os.path.join(temp_dir, "args.pkl"), 'wb') as f:
                args = self
                cloudpickle.dump(args, f)

            processes = self._run_subprocess(temp_dir)

            for _, process in enumerate(processes):
                process.wait()

            with open(os.path.join(temp_dir, "results.pkl"), "rb") as f:
                queue_list = cloudpickle.load(f)
                self.mp_queue = queue_loader(queue_list)
