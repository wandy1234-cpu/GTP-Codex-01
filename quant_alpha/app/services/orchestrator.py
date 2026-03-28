"""Service orchestrator used by GUI."""
from __future__ import annotations

from pipelines.backtest_pipeline import BacktestPipeline
from pipelines.data_pipeline import DataPipeline
from pipelines.predict_pipeline import PredictPipeline
from pipelines.train_pipeline import TrainPipeline


class Orchestrator:
    def update_data(self) -> str:
        df = DataPipeline().run()
        return f"数据更新完成: {len(df)} rows"

    def train_model(self) -> str:
        path = TrainPipeline().run()
        return f"模型训练完成: {path}"

    def run_predict(self) -> str:
        df = PredictPipeline().run()
        return f"预测完成: {len(df)} picks"

    def run_backtest(self) -> str:
        df = BacktestPipeline().run()
        return f"回测完成: {len(df)} folds"
