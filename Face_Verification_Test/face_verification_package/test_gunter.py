from face_verification import verify_documents


result = verify_documents(
    "../Gunter_Test"
)

print("=" * 70)
print("GUNTER TEST")
print("=" * 70)

print("Status:", result["status"])
print("Same person:", result["same_person"])
print("Reason:", result["reason"])

print("\nSuspicious documents:")

for document in result["suspicious_documents"]:
    print("-", document)

print("\nPairwise comparisons:")

for comparison in result["pairwise_comparisons"]:
    print(
        f"{comparison['file1']} ↔ "
        f"{comparison['file2']}: "
        f"{comparison['similarity']:.4f} → "
        f"{comparison['result']}"
    )