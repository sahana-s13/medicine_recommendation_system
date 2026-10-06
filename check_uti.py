import pandas as pd

# Load the dataset
df = pd.read_csv('data/training.csv')

# Exact disease name from the dataset
disease_name = 'Urinary tract infection'  

# Filter only UTI patients
uti_rows = df[df['prognosis'] == disease_name]

# Get all symptom columns (everything except 'prognosis')
symptom_cols = df.columns[:-1]

# Count how many UTI patients have each symptom (sum of 1s)
uti_symptom_counts = uti_rows[symptom_cols].sum()

# Symptoms that appear at least once in UTI
uti_present = uti_symptom_counts[uti_symptom_counts > 0]

# Symptoms that NEVER appear in UTI (always 0)
uti_not_present = uti_symptom_counts[uti_symptom_counts == 0]

# Print results
print(f"Total symptoms in dataset: {len(symptom_cols)}")
print(f"Symptoms that appear in UTI patients: {len(uti_present)}")
print(f"Symptoms that NEVER appear in UTI patients: {len(uti_not_present)}")

# Show a few examples of symptoms NOT associated with UTI
print("\n🔴 Examples of symptoms that have NO relationship with UTI:")
print(uti_not_present.head(10).index.tolist())

# Show a few examples of symptoms strongly associated with UTI
print("\n🟢 Top symptoms strongly associated with UTI:")
print(uti_present.sort_values(ascending=False).head(5))