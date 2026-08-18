from face_verification import verify_documents

# Run this from face_verification_package/ - path is relative to that.
# Application_New actually lives at New_Test/Application_New at the repo
# root, not directly under this package (this path was wrong before).
result = verify_documents("../../New_Test/Application_New")

print("Status:", result["status"])
print("Same person:", result["same_person"])
print("Reason:", result["reason"])
print("Suspicious documents:", result["suspicious_documents"])
