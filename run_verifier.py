import sys
from pathlib import Path

# Add the project package directory to Python's import path
PROJECT_ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = (
    PROJECT_ROOT
    / "Face_Verification_Test"
    / "face_verification_package"
)

sys.path.insert(0, str(PACKAGE_ROOT))

from face_verification.verifier import verify_documents


def main():
    if len(sys.argv) != 2:
        print("Usage:")
        print(
            r"python run_verifier.py "
            r"Face_Verification_Test\Melisent_Test"
        )
        sys.exit(1)

    folder = sys.argv[1]

    print("=" * 70)
    print("DOCUMENT FACE VERIFICATION")
    print("=" * 70)
    print("Folder:", folder)

    try:
        result = verify_documents(folder)

    except Exception as error:
        print("\nERROR:")
        print(type(error).__name__, "-", error)
        sys.exit(1)

    print("\nStatus:", result["status"])
    print("Same person:", result["same_person"])
    print("Reason:", result["reason"])

    print(
        "\nDocuments analysed:",
        result["documents_analysed"],
    )

    print("\nSuspicious documents:")

    suspicious = result.get(
        "suspicious_documents",
        [],
    )

    if suspicious:
        for document in suspicious:
            print("-", document)
    else:
        print("None")

    print("\nPairwise comparisons:")

    for comparison in result.get(
        "pairwise_comparisons",
        [],
    ):
        print(
            f'{comparison["file1"]} ↔ '
            f'{comparison["file2"]}: '
            f'{comparison["similarity"]:.4f} → '
            f'{comparison["result"]}'
        )


if __name__ == "__main__":
    main()