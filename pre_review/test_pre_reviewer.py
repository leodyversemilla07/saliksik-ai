from ai_processor import ManuscriptPreReviewer
import os


def main():
    pre_reviewer = ManuscriptPreReviewer()

    # Option 1: Test with plain text
    manuscript_text = """
    Artificial Intelligence (AI) is rapidly transforming the field of technology. 
    This manuscript discusses various advancements in AI, including neural networks, 
    machine learning, and their applications in real-world scenarios.
    """
    print("Testing with plain text...")
    report = pre_reviewer.generate_report(manuscript_text)
    print("Report:", report)

    # Option 2: Test with a PDF file
    print("\nTesting with PDF...")
    try:
        with open("sample_manuscript.pdf", "rb") as pdf_file:
            pdf_text = pre_reviewer.extract_text_from_pdf(pdf_file)
            report_from_pdf = pre_reviewer.generate_report(pdf_text)
            print("Report from PDF:", report_from_pdf)
    except FileNotFoundError:
        print(
            "Sample PDF file not found. Ensure 'sample_manuscript.pdf' is in the current directory."
        )


if __name__ == "__main__":
    main()
