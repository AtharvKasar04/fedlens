import difflib
import re

def compute_text_diff(old_text: str, new_text: str) -> str:
    """
    Computes a human-readable diff between two texts.
    Returns a string where additions are wrapped in [ADDED]...[/ADDED]
    and deletions are wrapped in [DELETED]...[/DELETED].
    """
    # Tokenize by words for a cleaner diff than characters
    old_words = re.findall(r'\S+|\n', old_text)
    new_words = re.findall(r'\S+|\n', new_text)
    
    matcher = difflib.SequenceMatcher(None, old_words, new_words)
    
    diff_output = []
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            diff_output.append(" ".join(old_words[i1:i2]))
        elif tag == 'replace':
            diff_output.append(f"[DELETED] {' '.join(old_words[i1:i2])} [/DELETED]")
            diff_output.append(f"[ADDED] {' '.join(new_words[j1:j2])} [/ADDED]")
        elif tag == 'delete':
            diff_output.append(f"[DELETED] {' '.join(old_words[i1:i2])} [/DELETED]")
        elif tag == 'insert':
            diff_output.append(f"[ADDED] {' '.join(new_words[j1:j2])} [/ADDED]")
            
    # Clean up spacing around newlines
    result = " ".join(diff_output)
    result = result.replace(" \n ", "\n").replace(" \n", "\n").replace("\n ", "\n")
    return result

def extract_meaningful_changes(diff_text: str) -> str:
    """
    Extracts only the sentences or phrases that contain changes, 
    to feed to the LLM so it isn't distracted by boilerplate.
    """
    # Simple extraction: grab a window around tags
    # For MVP, we will just pass the raw diff text to the LLM if it's short enough, 
    # but FOMC statements are only ~400 words, so passing the full diff is perfect.
    return diff_text
