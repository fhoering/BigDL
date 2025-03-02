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

import tempfile
from unittest import TestCase
import pytest
import torch
import os
import pandas as pd
import numpy as np

from torch.utils.data import TensorDataset, DataLoader
from bigdl.chronos.autots import TSPipeline
from bigdl.chronos.data import TSDataset


def train_data_creator(config):
    return DataLoader(TensorDataset(torch.randn(1000,
                                                config.get('past_seq_len', 10),
                                                config.get('input_feature_num', 2)),
                                    torch.randn(1000,
                                                config.get('future_seq_len', 2),
                                                config.get('output_feature_num', 2))),
                      batch_size=config.get('batch_size', 32), shuffle=True)

def valid_data_creator(config):
    return DataLoader(TensorDataset(torch.randn(1000,
                                                config.get('past_seq_len', 10),
                                                config.get('input_feature_num', 2)),
                                    torch.randn(1000,
                                                config.get('future_seq_len', 2),
                                                config.get('output_feature_num', 2))),
                      batch_size=config.get('batch_size', 32), shuffle=False)

def get_ts_df():
    sample_num = np.random.randint(100, 200)
    train_df = pd.DataFrame({"datetime": pd.date_range('1/1/2019', periods=sample_num),
                             "value 1": np.random.randn(sample_num),
                             "value 2": np.random.randn(sample_num),
                             "id": np.array(['00'] * sample_num),
                             "extra feature 1": np.random.randn(sample_num),
                             "extra feature 2": np.random.randn(sample_num)})
    return train_df

def get_test_tsdataset():
    df = get_ts_df()
    return TSDataset.from_pandas(df,
                                 dt_col="datetime",
                                 target_col=["value 1", "value 2"],
                                 extra_feature_col=["extra feature 1", "extra feature 2"],
                                 id_col="id")

class TestTSPipeline(TestCase):

    def setUp(self) -> None:
        self.resource_path = os.path.join(os.path.split(__file__)[0], "../resources/")

    def tearDown(self) -> None:
        pass

    def test_seq2seq_tsppl_support_dataloader(self):
        # load
        tsppl_seq2seq = TSPipeline.load(
            os.path.join(self.resource_path, "tsppl_ckpt/s2s_tsppl_ckpt"))
        tsppl_seq2seq.fit(data=train_data_creator,
                          validation_data=valid_data_creator,
                          epochs=2,
                          batch_size=128)
        assert tsppl_seq2seq._best_config['batch_size'] == 128
        config = tsppl_seq2seq._best_config
        # predict
        yhat = tsppl_seq2seq.predict(valid_data_creator, batch_size=16)
        assert yhat.shape == (1000,
                              config['future_seq_len'],
                              config['input_feature_num'])
        assert tsppl_seq2seq._best_config['batch_size'] == 16
        yhat = tsppl_seq2seq.predict_with_onnx(valid_data_creator, batch_size=64)
        assert yhat.shape == (1000,
                              config['future_seq_len'],
                              config['input_feature_num'])
        assert tsppl_seq2seq._best_config['batch_size'] == 64

        # evaluate
        _, smape = tsppl_seq2seq.evaluate(valid_data_creator,
                                          metrics=['mse', 'smape'],
                                          batch_size=16)
        assert tsppl_seq2seq._best_config['batch_size'] == 16
        assert smape < 2.0
        _, smape = tsppl_seq2seq.evaluate_with_onnx(valid_data_creator,
                                                    metrics=['mse', 'smape'],
                                                    batch_size=64)
        assert tsppl_seq2seq._best_config['batch_size'] == 64
        assert smape < 2.0

        # evaluate with customized metrics
        from torchmetrics.functional import mean_squared_error
        def customized_metric(y_true, y_pred):
            return mean_squared_error(torch.from_numpy(y_pred),
                                      torch.from_numpy(y_true)).numpy()
        tsppl_seq2seq.evaluate(valid_data_creator,
                               metrics=[customized_metric],
                               batch_size=16)
        assert tsppl_seq2seq._best_config['batch_size'] == 16

        with pytest.raises(RuntimeError):
            tsppl_seq2seq.predict(torch.randn(1000,
                                  config['past_seq_len'],
                                  config['input_feature_num']))
        with pytest.raises(RuntimeError):
            tsppl_seq2seq.evaluate(torch.randn(1000,
                                   config['past_seq_len'],
                                   config['input_feature_num']))

    def test_tcn_tsppl_support_dataloader(self):
        # load
        tsppl_tcn = TSPipeline.load(
            os.path.join(self.resource_path, "tsppl_ckpt/tcn_tsppl_ckpt"))
        tsppl_tcn.fit(data=train_data_creator,
                      validation_data=valid_data_creator,
                      epochs=2,
                      batch_size=128)
        assert tsppl_tcn._best_config['batch_size'] == 128
        config = tsppl_tcn._best_config
        yhat = tsppl_tcn.predict(data=valid_data_creator, batch_size=16)
        assert tsppl_tcn._best_config['batch_size'] == 16
        assert yhat.shape == (1000,
                              config['future_seq_len'],
                              config['output_feature_num'])

        _, smape = tsppl_tcn.evaluate(data=valid_data_creator,
                                      metrics=['mse', 'smape'],
                                      batch_size=64)
        assert tsppl_tcn._best_config['batch_size'] == 64
        assert smape < 2.0

    def test_lstm_tsppl_support_dataloader(self):
        # load
        tsppl_lstm = TSPipeline.load(
            os.path.join(self.resource_path, "tsppl_ckpt/lstm_tsppl_ckpt"))
        tsppl_lstm.fit(data=train_data_creator,
                       validation_data=valid_data_creator,
                       epochs=2,
                       batch_size=128)
        assert tsppl_lstm._best_config['batch_size'] == 128
        config = tsppl_lstm._best_config
        yhat = tsppl_lstm.predict(data=valid_data_creator, batch_size=16)
        assert tsppl_lstm._best_config['batch_size'] == 16
        assert yhat.shape == (1000,
                              config['future_seq_len'],
                              config['output_feature_num'])
        _, smape = tsppl_lstm.evaluate(data=valid_data_creator,
                              metrics=['mse', 'smape'],
                              batch_size=64)
        assert tsppl_lstm._best_config['batch_size'] == 64
        assert smape < 2.0

    def test_tsppl_mixed_data_type_usage(self):
        # This ckpt is generated by fit on a data creator
        tsppl_lstm = TSPipeline.load(
            os.path.join(self.resource_path, "tsppl_ckpt/lstm_tsppl_ckpt"))
        with pytest.raises(TypeError):
            yhat = tsppl_lstm.predict(data=get_test_tsdataset(), batch_size=16)

if __name__ == "__main__":
    pytest.main([__file__])
