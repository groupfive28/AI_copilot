# Current experimental threshold calibrated from the project's
# development/test comparisons. This is not a universal biometric
# threshold and should be re-evaluated as the validation dataset grows.
#
# This is the borderline-match cutoff that verifier.py actually reads
# (imported into verifier.py and used as the default for
# verify_documents(threshold=...)); the strong-match cutoff is derived
# from it as MATCH_THRESHOLD + 0.10, not set separately here.

MATCH_THRESHOLD = 0.20
