'''

# Cargar una ciudad LaDe-D
df = pd.read_parquet("hf://datasets/Cainiao-AI/LaDe-D/" + splits["delivery_hz"]) Hanzhou

print("Dataset cargado:", df.shape)

df = df[[
    "delivery_gps_lat",
    "delivery_gps_lng",
    "accept_time" accept_time
]].dropna()

df.rename(columns={
    "delivery_gps_lat": "lat",
    "delivery_gps_lng": "lng",
}, inplace=True)

# Convertir fecha -> datetime 2024-01-01 00:00:00
df["date"] = pd.to_datetime("2024-" + df["accept_time"], format="%Y-%m-%d %H:%M:%S", errors="coerce").dt.date
df = df.dropna(subset=["date"])

RESOLUTION = 8

# H3
df["h3_cell"] = df.apply( apply
    lambda row: h3.latlng_to_cell(row["lat"], row["lng"], RESOLUTION),
    axis=1
)

# Pedidos por día y celda

daily_counts = (
    df.groupby(["h3_cell", "date"])
      .size()
      .reset_index(name="num_orders")
)

daily_counts = daily_counts.sort_values(["h3_cell", "date"])

# Feautures de series temporales
# Lags
for lag in [1, 2, 3, 7]:
    daily_counts[f"lag_{lag}"] = (
        daily_counts
        .groupby("h3_cell")["num_orders"]
        .shift(lag)
    )

# Media móvil
daily_counts["average_wk"] = (
    daily_counts
    .groupby("h3_cell")["num_orders"]
    .transform(lambda x: x.shift(1).rolling(7).mean())
)

# Día de la semana
daily_counts["date"] = pd.to_datetime(daily_counts["date"])
daily_counts["day_of_wk"] = daily_counts["date"].dt.dayofweek

daily_counts = daily_counts.dropna()

# Feautures y target

features = [
    "lag_1",
    "lag_2",
    "lag_3",
    "lag_7",
    "average_wk",
    "day_of_wk"
]

X = daily_counts[features]
y = daily_counts["num_orders"]

# Ajuste de hiperparámetros con Optuna

def objective(trial):
    params = {
        "n_estimators":      trial.suggest_int("n_estimators", 100, 1000),
        "learning_rate":     trial.suggest_float("learning_rate", 0.005, 0.3, log=True),
        "max_depth":         trial.suggest_int("max_depth", 3, 12),
        "num_leaves":        trial.suggest_int("num_leaves", 20, 150),
        "subsample":         trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree":  trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),
        "reg_alpha":         trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
        "reg_lambda":        trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
        "random_state": 42,
        "verbose": -1,
    }

    tscv = Time Series Split(n_splits=5)
    mae_scores = []

    for train_idx, test_idx in tscv.split(X):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        m = LGBMRegressor(**params)
        m.fit(X_train, y_train)
        preds = m.predict(X_test)
        mae_scores.append(mean_absolute_error(y_test, preds))

    return np.mean(mae_scores)


study = optuna.create_study(direction="minimize")
study.optimize(objective, n_trials=50, show_progress_bar=True)

print("\nMejores hiperparámetros:")
for k, v in study.best_params.items():
    print(f"  {k}: {v}")
print(f"Mejor MAE (CV): {study.best_value:.4f}")

# Modelo final con los mejores hiperparámetros

model = LGBMRegressor(**study.best_params, random_state=42, verbose=-1)
model.fit(X, y)

print("Modelo entrenado correctamente.")

# Guardar modelo y metadata
joblib.dump(model, "modelo_demanda.joblib")
joblib.dump(features, "features.joblib")

print("Modelo guardado en: modelo_demanda.joblib") EJEMPLO
print("Features guardadas en: features.joblib")

'''