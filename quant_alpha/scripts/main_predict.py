from pipelines.predict_pipeline import PredictPipeline
from pipelines.train_pipeline import TrainPipeline

if __name__ == "__main__":
    TrainPipeline().run()
    df = PredictPipeline().run()
    print(df)
