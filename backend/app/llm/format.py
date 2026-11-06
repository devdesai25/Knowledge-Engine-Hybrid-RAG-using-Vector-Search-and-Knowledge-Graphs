def format_chunk(text, page_no, headings) -> str:

#    print(vars(chunk))
    meta = text
    header_parts=[]

    if page_no:
        header_parts.append(f"Document: {page_no}")
    if headings:
        header_parts.append(f"Document: {headings}")

    header = " | ".join(header_parts)

    return f"[{header}]\n{text}" 