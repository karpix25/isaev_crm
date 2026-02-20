def recursive_text_split(text: str, max_chunk_size: int = 1200, overlap: int = 200):
    separators = ["\n\n", "\n", ". ", " "]
    
    def get_splits(text, separators):
        if not text: return []
        if not separators: return [text]
        sep = separators[0]
        if sep not in text:
            return get_splits(text, separators[1:])
            
        parts = text.split(sep)
        res = []
        for i, p in enumerate(parts):
            sub_p = p + (sep if i < len(parts) - 1 else "")
            if len(sub_p) > max_chunk_size:
                res.extend(get_splits(sub_p, separators[1:]))
            else:
                res.append(sub_p)
        return res

    parts = get_splits(text, separators)
    
    # Merge parts with overlap
    chunks = []
    current_chunk = ""
    
    for part in parts:
        if len(current_chunk) + len(part) <= max_chunk_size:
            current_chunk += part
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            # For overlap, keep the last 'overlap' characters of current_chunk
            if current_chunk and overlap > 0:
                overlap_start = max(0, len(current_chunk) - overlap)
                overlap_text = current_chunk[overlap_start:]
                # try to find a safe boundary
                safe_idx = overlap_text.find(" ")
                if safe_idx != -1:
                    overlap_text = overlap_text[safe_idx:]
                current_chunk = overlap_text + part
            else:
                current_chunk = part
                
    if current_chunk:
        chunks.append(current_chunk.strip())
        
    return [c for c in chunks if len(c) > 20]

test_txt = "A" * 1000 + "\n\n" + "B" * 600 + "\n" + "C" * 300
chunks = recursive_text_split(test_txt, 1200, 200)
for i, c in enumerate(chunks):
    print(i, len(c))
