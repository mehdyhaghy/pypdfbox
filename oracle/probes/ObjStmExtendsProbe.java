import java.io.File;
import java.io.PrintStream;
import java.util.Map;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for object streams chained via ``/Extends``.
 *
 * PDF 32000-1 §7.5.7: an object stream's ``/Extends`` entry references a
 * prior object stream, forming a chain. The chain is purely informational
 * for *lookup* — a 1.5+ reader resolves each compressed object through the
 * container named by that object's cross-reference-stream type-2 entry
 * (``container number, index``), NOT by walking ``/Extends``. ``/Extends``
 * matters for object-stream *generation* / regeneration and for readers that
 * must enumerate every object in a chain. This probe pins the read-side
 * invariant: every object in a multi-level ``/Extends`` chain (A extends B
 * extends C), with multiple objects packed per container, resolves to the
 * identical dictionary, page count, and text PDFBox produces — and the raw
 * cross-reference value PDFBox stored (negative => compressed; magnitude is
 * the home container object number) matches pypdfbox's, so each object is
 * routed to the correct home ObjStm regardless of chain depth.
 *
 * Mode (one ``key=value`` per line; ``text=`` is emitted last, verbatim):
 *
 *   facts file.pdf objnum [objnum ...]
 *       pages              = page count
 *       resolved_N         = true|false (object N resolved to non-null)
 *       type_N             = /Type name (or empty)
 *       marker_N           = /Marker string value (or empty)
 *       value_N            = /Value integer (or -1)
 *       xref_N             = raw COSDocument.getXrefTable() value for key N:0
 *                            (negative => compressed in container |value|)
 *       text               = PDFTextStripper output, raw, last on stdout
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> ObjStmExtendsProbe facts file.pdf 6 9 11
 */
public final class ObjStmExtendsProbe {
    public static void main(String[] args) throws Exception {
        if (!"facts".equals(args[0])) {
            throw new IllegalArgumentException("unknown mode: " + args[0]);
        }
        String file = args[1];
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        COSName marker = COSName.getPDFName("Marker");
        COSName value = COSName.getPDFName("Value");
        try (PDDocument doc = Loader.loadPDF(new File(file))) {
            sb.append("pages=").append(doc.getNumberOfPages()).append("\n");
            Map<COSObjectKey, Long> xref = doc.getDocument().getXrefTable();
            for (int i = 2; i < args.length; i++) {
                int num = Integer.parseInt(args[i]);
                COSObjectKey key = new COSObjectKey(num, 0);
                COSObject obj = doc.getDocument().getObjectFromPool(key);
                COSBase base = obj == null ? null : obj.getObject();
                sb.append("resolved_").append(num).append("=")
                  .append(base != null ? "true" : "false").append("\n");
                if (base instanceof COSDictionary) {
                    COSDictionary d = (COSDictionary) base;
                    COSBase t = d.getDictionaryObject(COSName.TYPE);
                    sb.append("type_").append(num).append("=")
                      .append(t instanceof COSName ? ((COSName) t).getName() : "")
                      .append("\n");
                    sb.append("marker_").append(num).append("=")
                      .append(d.getString(marker, "")).append("\n");
                    sb.append("value_").append(num).append("=")
                      .append(d.getInt(value, -1)).append("\n");
                }
                Long off = xref.get(key);
                sb.append("xref_").append(num).append("=")
                  .append(off == null ? "absent" : off.toString()).append("\n");
            }
            String text = new PDFTextStripper().getText(doc);
            sb.append("text=").append(text);
        }
        out.print(sb);
    }
}
