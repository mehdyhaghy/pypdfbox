import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for PDF 1.5 hybrid-reference parsing and /Extends ObjStm
 * chains on the READ side.
 *
 * A hybrid-reference file (PDF 32000-1 §7.5.8.4) carries BOTH a classic xref
 * table and a cross-reference stream pointed at by the trailer's /XRefStm key.
 * Objects that exist only in the /XRefStm (typically packed in an ObjStm and
 * marked free/absent in the classic table) are invisible to a legacy
 * table-only reader; a 1.5+ reader must consult /XRefStm to resolve them.
 *
 * Separately, an object stream can chain to a prior one via /Extends; an object
 * routed (by its xref entry) into the extending ObjStm must resolve through
 * that container even though the base ObjStm is what /Extends references.
 *
 * Modes (one "key=value" per line on stdout; the text= line is emitted last and
 * verbatim):
 *
 *   facts file.pdf objnum [objnum2]
 *       pages    = page count
 *       text     = PDFTextStripper output, raw on its own line(s)
 *       resolved_<objnum> = true|false  (object dereferences to non-null)
 *       type_<objnum>     = the /Type name of the resolved dictionary
 *       marker_<objnum>   = the /Marker string of the resolved dictionary
 *       value_<objnum>    = the /Value integer of the resolved dictionary
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> HybridXrefProbe facts file.pdf 6
 *   java -cp <pdfbox-app.jar>:<build> HybridXrefProbe facts file.pdf 6 9
 */
public final class HybridXrefProbe {
    public static void main(String[] args) throws Exception {
        if (!"facts".equals(args[0])) {
            throw new IllegalArgumentException("unknown mode: " + args[0]);
        }
        String file = args[1];
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(new File(file))) {
            sb.append("pages=").append(doc.getNumberOfPages()).append("\n");
            for (int i = 2; i < args.length; i++) {
                long objNum = Long.parseLong(args[i]);
                emitObject(doc, objNum, sb);
            }
            String text = new PDFTextStripper().getText(doc);
            sb.append("text=").append(text);
        }
        out.print(sb);
    }

    private static void emitObject(PDDocument doc, long objNum, StringBuilder sb) {
        COSObject obj = doc.getDocument().getObjectFromPool(new COSObjectKey(objNum, 0));
        COSBase base = (obj != null) ? obj.getObject() : null;
        sb.append("resolved_").append(objNum).append("=")
          .append(base != null).append("\n");
        if (base instanceof COSDictionary) {
            COSDictionary dict = (COSDictionary) base;
            COSBase type = dict.getDictionaryObject(COSName.TYPE);
            sb.append("type_").append(objNum).append("=")
              .append(type instanceof COSName ? ((COSName) type).getName() : "")
              .append("\n");
            COSBase marker = dict.getDictionaryObject(COSName.getPDFName("Marker"));
            sb.append("marker_").append(objNum).append("=")
              .append(marker instanceof COSString ? ((COSString) marker).getString() : "")
              .append("\n");
            COSBase value = dict.getDictionaryObject(COSName.getPDFName("Value"));
            sb.append("value_").append(objNum).append("=")
              .append(value instanceof COSNumber ? ((COSNumber) value).intValue() : -1)
              .append("\n");
        }
    }
}
