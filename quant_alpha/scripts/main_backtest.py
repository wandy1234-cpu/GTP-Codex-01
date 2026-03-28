from pipelines.backtest_pipeline import BacktestPipeline

if __name__ == "__main__":
    df = BacktestPipeline().run()
    print(df)
