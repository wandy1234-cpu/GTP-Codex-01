from pipelines.data_pipeline import DataPipeline

if __name__ == "__main__":
    df = DataPipeline().run()
    print(f"updated rows={len(df)}")
