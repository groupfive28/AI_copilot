from face_verification import verify_documents

result = verify_documents("Application_New")

print("Status:", result["status"])
print("Same person:", result["same_person"])
print("Reason:", result["reason"])
print("Suspicious documents:", result["suspicious_documents"])
