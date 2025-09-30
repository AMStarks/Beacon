#!/usr/bin/env python3
"""
Debug the post-processing step
"""

from advanced_excerpt_generator import AdvancedExcerptGenerator

def debug_postprocessing():
    print("🔍 Debugging post-processing...")
    
    gen = AdvancedExcerptGenerator()
    
    # Test with a sample excerpt
    sample_excerpt = "The Liberal party will alienate more women and young people if it abandons net zero, several Liberal women have warned, as the party publicly fractures over its energy policy. Weeks after Andrew Hastie threatened to quit the frontbench if the Coalition embraced net zero, three high-profile current and former senior Liberal women have warned going backwards on climate action will only hurt the party more with key demographics. Maria Kovacic, recently promoted to Sussan Ley's shadow ministry, said women and young people had already abandoned the party at the last election."
    
    print(f"Original excerpt: {sample_excerpt}")
    print(f"Word count: {len(sample_excerpt.split())}")
    
    result = gen._post_process_summary(sample_excerpt)
    print(f"Post-processed: {result}")
    print(f"Final word count: {len(result.split())}")

if __name__ == "__main__":
    debug_postprocessing()
