def format_chunk(chunk) -> str:

#    print(vars(chunk))
    meta = chunk.payload['meta']
    header_parts=[]

    if meta.get("page_no"):
        header_parts.append(f"Document: {meta['page_no']}")
    if meta.get("headings"):
        header_parts.append(f"Document: {meta['headings']}")

    header = " | ".join(header_parts)

    return f"[{header}]\n{chunk.payload['text']}" if header else chunk.text