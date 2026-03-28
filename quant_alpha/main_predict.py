"""CLI entry for prediction."""
from pipelines.predict_pipeline import PredictPipeline
from pipelines.train_pipeline import TrainPipeline

if __name__ == "__main__":
    TrainPipeline().run()
    picks = PredictPipeline().run()
    print(picks.to_string(index=False))
