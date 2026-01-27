"""
Performance Benchmarking Script for Saliksik AI v2.1.0

Tests:
1. Plagiarism Detection - Document fingerprinting and similarity checking
2. Reviewer Matching - Keyword and semantic similarity calculations
3. Citation Analysis - Reference parsing performance
4. Language Detection - Multi-language detection speed

Run with: python tests/benchmark_performance.py
"""

import time
import sys
import os
import statistics

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def generate_sample_text(word_count: int) -> str:
    """Generate sample academic text of specified word count."""
    base_text = """
    The study of machine learning has revolutionized various fields of computer science.
    Deep neural networks have shown remarkable performance in image classification tasks.
    Natural language processing enables computers to understand human language.
    The methodology employed in this research follows established scientific protocols.
    Results indicate significant improvements over baseline approaches.
    Statistical analysis confirms the validity of our experimental findings.
    Future work will explore more advanced architectures for this problem domain.
    The implications of these findings extend to practical applications.
    """
    words = base_text.split()
    result = []
    while len(result) < word_count:
        result.extend(words)
    return " ".join(result[:word_count])


def benchmark_plagiarism_detection():
    """Benchmark plagiarism detection service."""
    print("\n" + "=" * 60)
    print("PLAGIARISM DETECTION BENCHMARKS")
    print("=" * 60)
    
    try:
        from app.services.plagiarism_detector import PlagiarismDetector
        detector = PlagiarismDetector()
        
        # Test different document sizes
        sizes = [500, 1000, 2500, 5000, 10000]
        
        print(f"\n{'Doc Size (words)':<20} {'Fingerprint (ms)':<20} {'Shingles':<15}")
        print("-" * 55)
        
        results = []
        for size in sizes:
            text = generate_sample_text(size)
            
            # Benchmark fingerprinting
            start = time.perf_counter()
            shingles = detector._create_shingles(text)
            fingerprint_time = (time.perf_counter() - start) * 1000
            
            results.append({
                'size': size,
                'fingerprint_ms': fingerprint_time,
                'shingles': len(shingles)
            })
            
            print(f"{size:<20} {fingerprint_time:<20.2f} {len(shingles):<15}")
        
        # Add to index benchmark
        print(f"\n{'Operation':<30} {'Time (ms)':<20}")
        print("-" * 50)
        
        text = generate_sample_text(5000)
        start = time.perf_counter()
        detector.add_to_index(doc_id=1, text=text, filename="test.pdf")
        add_time = (time.perf_counter() - start) * 1000
        print(f"{'Add to index (5k words)':<30} {add_time:<20.2f}")
        
        # Add more documents for similarity check
        for i in range(2, 11):
            detector.add_to_index(doc_id=i, text=generate_sample_text(3000), filename=f"doc{i}.pdf")
        
        # Check similarity
        query_text = generate_sample_text(5000) + " unique content here for testing"
        start = time.perf_counter()
        similar = detector.check_similarity(query_text)
        check_time = (time.perf_counter() - start) * 1000
        print(f"{'Check similarity (10 docs)':<30} {check_time:<20.2f}")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False


def benchmark_reviewer_matching():
    """Benchmark reviewer matching service."""
    print("\n" + "=" * 60)
    print("REVIEWER MATCHING BENCHMARKS")
    print("=" * 60)
    
    try:
        from app.services.reviewer_matcher import ReviewerMatcher
        matcher = ReviewerMatcher()
        
        # Test keyword similarity
        manuscript_keywords = ["machine learning", "neural networks", "deep learning", "computer vision", "nlp"]
        reviewer_keywords = ["artificial intelligence", "machine learning", "data science", "deep learning"]
        
        print(f"\n{'Operation':<40} {'Time (ms)':<20}")
        print("-" * 60)
        
        # Keyword similarity
        times = []
        for _ in range(100):
            start = time.perf_counter()
            score, matched = matcher.calculate_keyword_similarity(manuscript_keywords, reviewer_keywords)
            times.append((time.perf_counter() - start) * 1000)
        
        avg_time = statistics.mean(times)
        print(f"{'Keyword similarity (avg of 100)':<40} {avg_time:<20.4f}")
        
        # Hybrid score calculation
        times = []
        for _ in range(100):
            start = time.perf_counter()
            hybrid = matcher.calculate_hybrid_score(0.8, 0.6, 0.5)
            times.append((time.perf_counter() - start) * 1000)
        
        avg_time = statistics.mean(times)
        print(f"{'Hybrid score calc (avg of 100)':<40} {avg_time:<20.6f}")
        
        # Embedding creation (if available)
        try:
            start = time.perf_counter()
            embedding = matcher.create_expertise_embedding(
                reviewer_keywords,
                "Expert in AI and machine learning research"
            )
            embed_time = (time.perf_counter() - start) * 1000
            
            if embedding is not None:
                print(f"{'Create expertise embedding':<40} {embed_time:<20.2f}")
            else:
                print(f"{'Create expertise embedding':<40} {'N/A (no model)':<20}")
        except Exception:
            print(f"{'Create expertise embedding':<40} {'N/A (model error)':<20}")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False


def benchmark_citation_analysis():
    """Benchmark citation analysis service."""
    print("\n" + "=" * 60)
    print("CITATION ANALYSIS BENCHMARKS")
    print("=" * 60)
    
    try:
        from app.services.citation_analyzer import CitationAnalyzer
        analyzer = CitationAnalyzer()
        
        # Sample academic text with citations
        sample_text = """
        According to Smith et al. (2020), machine learning has transformed the field.
        Previous research (Johnson & Williams, 2019) demonstrated similar findings.
        As noted by Brown (2018, p. 45), the methodology is well-established.
        
        References
        
        Brown, A. B. (2018). Introduction to research methods. Academic Press.
        Johnson, C. D., & Williams, E. F. (2019). Deep learning fundamentals. Journal of AI Research, 15(3), 200-225.
        Smith, G. H., Lee, I. J., & Park, K. L. (2020). Machine learning applications. Nature Machine Intelligence, 2(1), 50-65.
        """
        
        print(f"\n{'Operation':<40} {'Time (ms)':<20}")
        print("-" * 60)
        
        # Format detection
        times = []
        for _ in range(100):
            start = time.perf_counter()
            format_detected = analyzer.detect_format(sample_text)
            times.append((time.perf_counter() - start) * 1000)
        
        avg_time = statistics.mean(times)
        print(f"{'Format detection (avg of 100)':<40} {avg_time:<20.4f}")
        print(f"  Detected format: {format_detected}")
        
        # Full analysis
        start = time.perf_counter()
        result = analyzer.analyze(sample_text)
        analysis_time = (time.perf_counter() - start) * 1000
        print(f"{'Full citation analysis':<40} {analysis_time:<20.2f}")
        print(f"  References found: {len(result.references)}")
        print(f"  Total citations: {result.total_citations}")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False


def benchmark_language_detection():
    """Benchmark language detection service."""
    print("\n" + "=" * 60)
    print("LANGUAGE DETECTION BENCHMARKS")
    print("=" * 60)
    
    try:
        from app.services.language_detector import LanguageDetector
        detector = LanguageDetector()
        
        samples = {
            "English": "This is a sample text for testing language detection capabilities.",
            "Spanish": "Este es un texto de ejemplo para probar las capacidades de detección de idiomas.",
            "French": "Ceci est un texte d'exemple pour tester les capacités de détection de langue.",
            "German": "Dies ist ein Beispieltext zum Testen der Spracherkennungsfunktionen.",
        }
        
        print(f"\n{'Language':<15} {'Time (ms)':<15} {'Detected':<15} {'Confidence':<15}")
        print("-" * 60)
        
        for lang_name, text in samples.items():
            times = []
            for _ in range(50):
                start = time.perf_counter()
                result = detector.detect_language(text)
                times.append((time.perf_counter() - start) * 1000)
            
            avg_time = statistics.mean(times)
            print(f"{lang_name:<15} {avg_time:<15.2f} {result.name:<15} {result.confidence:<15.2f}")
        
        # Supported languages
        supported = detector.get_supported_languages()
        print(f"\nSupported languages: {len(supported)}")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    """Run all benchmarks."""
    print("=" * 60)
    print("SALIKSIK AI v2.1.0 - PERFORMANCE BENCHMARKS")
    print("=" * 60)
    print(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {
        "Plagiarism Detection": benchmark_plagiarism_detection(),
        "Reviewer Matching": benchmark_reviewer_matching(),
        "Citation Analysis": benchmark_citation_analysis(),
        "Language Detection": benchmark_language_detection(),
    }
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for service, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{service:<30} {status}")
    
    print("\n" + "=" * 60)
    print("BENCHMARK COMPLETE")
    print("=" * 60)
    
    return all(results.values())


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
