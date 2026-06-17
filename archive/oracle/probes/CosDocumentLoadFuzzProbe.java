import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Differential fuzz probe for Apache PDFBox 3.0.7 document-level accessors on a
 * PARSED (populated) {@code org.apache.pdfbox.cos.COSDocument}. Wave 1561, agent B.
 *
 * <p>Where the wave-1537 {@code CosDocumentFuzzProbe} built fresh/empty docs in
 * memory and probed the lifecycle corners, this probe loads a real PDF file
 * (built by the pypdfbox sibling test and handed in as {@code args[0]}) and
 * projects the accessors that only mean something once the parser has filled the
 * object pool, the xref table, and the trailer:
 *
 * <ul>
 *   <li>{@code getVersion} read from the {@code %PDF-x.y} header;</li>
 *   <li>{@code getTrailer} presence + {@code /Size};</li>
 *   <li>{@code getObjectsByType(name)} count for present types
 *       ({@code Page}, {@code Pages}, {@code Catalog}) and an absent one;</li>
 *   <li>the two-arg {@code getObjectsByType(name, alt)} overload;</li>
 *   <li>{@code isEncrypted} + {@code getEncryptionDictionary} presence;</li>
 *   <li>{@code getDocumentID} presence + element count (catches wrong /ID
 *       arity verbatim — upstream returns the array as-is);</li>
 *   <li>{@code getXrefTable} size;</li>
 *   <li>{@code getObjectFromPool} for a present key (resolves a /Type) and an
 *       absent key (placeholder, null object);</li>
 *   <li>{@code getHighestXRefObjectNumber}.</li>
 * </ul>
 *
 * <p>Each result is one {@code KEY=VALUE} line (LF-terminated). The pypdfbox
 * sibling ({@code tests/cos/oracle/test_cos_document_fuzz_wave1561.py}) parses
 * the very same bytes and asserts byte-identical projections.
 */
public final class CosDocumentLoadFuzzProbe {

    static PrintStream out;

    static void line(String key, Object value) {
        out.println(key + "=" + value);
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument pd = Loader.loadPDF(new File(args[0]))) {
            COSDocument doc = pd.getDocument();

            line("version", floatStr(doc.getVersion()));

            COSDictionary trailer = doc.getTrailer();
            line("trailer", trailer == null ? "null" : "nonnull");
            line("size", trailer == null ? "null"
                    : Integer.toString(trailer.getInt(COSName.SIZE)));

            line("pageCount",
                    Integer.toString(doc.getObjectsByType(COSName.PAGE).size()));
            line("pagesCount",
                    Integer.toString(doc.getObjectsByType(COSName.PAGES).size()));
            line("catalogCount",
                    Integer.toString(doc.getObjectsByType(COSName.CATALOG).size()));
            line("absentCount",
                    Integer.toString(
                            doc.getObjectsByType(COSName.getPDFName("Nope")).size()));
            // Two-arg overload: count objects whose /Type is Page OR Pages.
            line("pageOrPagesCount",
                    Integer.toString(
                            doc.getObjectsByType(COSName.PAGE, COSName.PAGES).size()));

            line("isEncrypted", Boolean.toString(doc.isEncrypted()));
            line("encDict",
                    doc.getEncryptionDictionary() == null ? "null" : "nonnull");

            COSArray id = doc.getDocumentID();
            line("docId", id == null ? "null" : "nonnull");
            line("docIdSize", id == null ? "null" : Integer.toString(id.size()));

            line("xrefSize", Integer.toString(doc.getXrefTable().size()));
            line("highestXRef",
                    Long.toString(doc.getHighestXRefObjectNumber()));

            // Present key — object 1 is always the catalog in our fixtures.
            COSObject present = doc.getObjectFromPool(new COSObjectKey(1, 0));
            line("poolPresentNull",
                    present == null ? "null"
                            : (present.getObject() == null ? "objnull" : "objnonnull"));
            line("poolPresentType",
                    typeOf(present));

            // Absent key — far beyond any object in the fixture.
            COSObject absent = doc.getObjectFromPool(new COSObjectKey(9999, 0));
            line("poolAbsentNull",
                    absent == null ? "null"
                            : (absent.getObject() == null ? "objnull" : "objnonnull"));
        }
    }

    static String typeOf(COSObject obj) {
        if (obj == null) {
            return "null";
        }
        Object resolved = obj.getObject();
        if (resolved instanceof COSDictionary) {
            COSName t = ((COSDictionary) resolved).getCOSName(COSName.TYPE);
            return t == null ? "notype" : ("/" + t.getName());
        }
        return "nondict";
    }

    static String floatStr(float f) {
        return Float.toString(f);
    }
}
