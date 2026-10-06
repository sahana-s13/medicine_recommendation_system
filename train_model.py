import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.svm import SVC
import pickle

# Load dataset
data = pd.read_csv('data/training.csv')

# Separate features and target
X = data.iloc[:, :-1]   # all columns except last
y = data.iloc[:, -1]    # prognosis column

# Encode target (disease names -> integers)
encoder = LabelEncoder()
y_encoded = encoder.fit_transform(y)

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y_encoded, test_size=0.3, random_state=20)

# Train SVC (linear kernel)
model = SVC(kernel='linear')
model.fit(X_train, y_train)

# Save model and encoder
with open('models/svc_model.pkl', 'wb') as f:
    pickle.dump((model, encoder, X.columns.tolist()), f)   # also save feature names

print("Model trained and saved.")