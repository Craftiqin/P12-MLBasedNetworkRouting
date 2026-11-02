from ml.pipeline import train_model

if __name__ == "__main__":
    _, metrics, data = train_model()
    print(f"Saved {len(data)} synthetic observations to data/link_observations.csv")
    print("Saved model to models/delivery_tree.joblib")
    print(metrics)
