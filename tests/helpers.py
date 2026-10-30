def pdf_bytes(text):
    import fitz
    pdf=fitz.open(); page=pdf.new_page(); page.insert_text((60,70),text); result=pdf.tobytes(); pdf.close(); return result
