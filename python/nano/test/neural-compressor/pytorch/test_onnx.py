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


import pytest
import os
from unittest import TestCase
import tempfile

import torch
from torch import nn
from torch.utils.data import TensorDataset, DataLoader
import torchmetrics

import numpy as np

from _train_torch_lightning import create_data_loader, data_transform
from bigdl.nano.pytorch.trainer import Trainer
from bigdl.nano.pytorch.vision.models import vision

batch_size = 256
num_workers = 0
data_dir = os.path.join(os.path.dirname(__file__), "data")


class ResNet18(nn.Module):
    def __init__(self, num_classes, pretrained=True, include_top=False, freeze=True):
        super().__init__()
        backbone = vision.resnet18(pretrained=pretrained, include_top=include_top, freeze=freeze)
        output_size = backbone.get_output_size()
        head = nn.Linear(output_size, num_classes)
        self.model = nn.Sequential(backbone, head)

    def forward(self, x):
        return self.model(x)


class MultiInputModel(nn.Module):
    def __init__(self):
        super().__init__()

        self.layer_1 = nn.Linear(28 * 28, 128)
        self.layer_2 = nn.Linear(28 * 28, 128)
        self.layer_3 = nn.Linear(256, 2)

    def forward(self, x1, x2):
        x1 = self.layer_1(x1)
        x2 = self.layer_2(x2)
        x = torch.cat([x1, x2], axis=1)

        return self.layer_3(x)


class TestOnnx(TestCase):

    def test_trainer_compile_with_onnx(self):
        model = ResNet18(10, pretrained=False, include_top=False, freeze=True)
        loss = nn.CrossEntropyLoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
        trainer = Trainer(max_epochs=1)

        pl_model = Trainer.compile(model, loss, optimizer, onnx=True)
        train_loader = create_data_loader(data_dir, batch_size, \
                                          num_workers, data_transform, subset=200)
        trainer.fit(pl_model, train_loader)

        for x, y in train_loader:
            onnx_res = pl_model.inference(x.numpy())  # onnxruntime
            pytorch_res = pl_model.inference(x.numpy(), backend=None).numpy()  # native pytorch
            pl_model.eval_onnx()
            forward_res = pl_model(x).numpy()
            pl_model.exit_onnx()
            np.testing.assert_almost_equal(onnx_res, pytorch_res, decimal=5)  # same result
            np.testing.assert_almost_equal(onnx_res, forward_res, decimal=5)  # same result

        trainer = Trainer(max_epochs=1)
        trainer.fit(pl_model, train_loader)

        pl_model.eval_onnx()  # update the ortsess with default settings

        for x, y in train_loader:
            pl_model.inference(x.numpy())

    def test_multiple_input_onnx(self):
        model = MultiInputModel()
        loss = nn.CrossEntropyLoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
        trainer = Trainer(max_epochs=1)

        pl_model = Trainer.compile(model, loss, optimizer, onnx=True)
        x1 = torch.randn(100, 28 * 28)
        x2 = torch.randn(100, 28 * 28)
        y = torch.zeros(100).long()
        y[0:50] = 1
        train_loader = DataLoader(TensorDataset(x1, x2, y), batch_size=32, shuffle=True)
        trainer.fit(pl_model, train_loader)

        for x1, x2, y in train_loader:
            onnx_res = pl_model.inference([x1.numpy(), x2.numpy()])  # onnxruntime
            pytorch_res = pl_model.inference([x1.numpy(), x2.numpy()], backend=None).numpy()  # native pytorch
            pl_model.eval_onnx()
            forward_res = pl_model(x1, x2).numpy()
            pl_model.exit_onnx()
            np.testing.assert_almost_equal(onnx_res, pytorch_res, decimal=5)  # same result
            np.testing.assert_almost_equal(onnx_res, forward_res, decimal=5)  # same result

        trainer = Trainer(max_epochs=1)
        trainer.fit(pl_model, train_loader)

        pl_model.eval_onnx()  # update the ortsess with default settings

        for x1, x2, y in train_loader:
            pl_model.inference([x1.numpy(), x2.numpy()])

    def test_trainer_compile_with_onnx_quantize(self):
        model = ResNet18(10, pretrained=False, include_top=False, freeze=True)
        loss = nn.CrossEntropyLoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
        trainer = Trainer(max_epochs=1)

        pl_model = Trainer.compile(model, loss, optimizer, onnx=True)
        train_loader = create_data_loader(data_dir, batch_size, \
                                          num_workers, data_transform, subset=200)
        trainer.fit(pl_model, train_loader)

        # false framework parameters
        with pytest.raises(RuntimeError):
            pl_model = trainer.quantize(pl_model, train_loader,
                                        framework=['pytorch_fx', 'pytorch'])
        with pytest.raises(RuntimeError):
            pl_model = trainer.quantize(pl_model, train_loader,
                                        framework=['onnxrt_integerops', 'onnxrt_qlinearops'])

        # normal usage without tunning
        pl_model = trainer.quantize(pl_model, train_loader, framework=['pytorch_fx', 'onnxrt_integerops'])
        for x, y in train_loader:
            onnx_res = pl_model.inference(x.numpy(), backend="onnx", quantize=True).numpy()
            pl_model.eval_onnx(quantize=True)
            forward_res = pl_model(x).numpy()
            np.testing.assert_almost_equal(onnx_res, forward_res, decimal=5)  # same result

        # quantization with tunning
        pl_model.eval(quantize=False)
        pl_model = trainer.quantize(pl_model,
                                    calib_dataloader=train_loader,
                                    val_dataloader=train_loader,
                                    metric=torchmetrics.F1(10),
                                    framework=['onnxrt_qlinearops'],
                                    accuracy_criterion={'relative': 0.99,
                                                        'higher_is_better': True})
        for x, y in train_loader:
            onnx_res = pl_model.inference(x.numpy(), backend="onnx", quantize=True).numpy()
            pl_model.eval_onnx()
            forward_res = pl_model(x).numpy()
            np.testing.assert_almost_equal(onnx_res, forward_res, decimal=5)  # same result

        # save the quantized model
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            ckpt_name = os.path.join(tmp_dir_name, ".onnx")
            pl_model.to_quantized_onnx(ckpt_name)


if __name__ == '__main__':
    pytest.main([__file__])
