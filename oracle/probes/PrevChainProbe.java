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

/**
 * Live oracle probe for cross-reference ``/Prev`` chain resolution across
 * MULTIPLE stacked incremental updates, each written as a CLASSIC
 * ``xref...trailer`` section.
 *
 * PDF 32000-1 §7.5.6 — an incremental update appends a new body + a new xref
 * section whose ``/Prev`` points at the previous section. The parser walks the
 * chain newest→oldest; for any object number the entry from the MOST RECENT
 * section that mentions it wins (later sections shadow earlier ones). An object
 * marked free (``f``) in a later section is gone even though an earlier section
 * defined it (``n``).
 *
 * Layout exercised by the paired test:
 *   rev1 — objects 1..6 (catalog, pages, page, contents, font, marker 6).
 *   rev2 — redefines object 6 (new value/tag) and adds object 7.
 *   rev3 — redefines object 7 (new value) and FREES object 6.
 *
 * So in the resolved document: object 6 must be GONE (freed in rev3), and
 * object 7 must carry rev3's value (not rev2's).
 *
 * Mode (one "key=value" per line on stdout):
 *   facts file.pdf objnum [objnum2 ...]
 *       pages           = page count
 *       root            = /Root object number (as "n g")
 *       object_count    = COSDocument.getXrefTable().size()  (pool reach)
 *       resolved_<n>    = true|false  (object dereferences to non-null)
 *       type_<n>        = the /Type name of the resolved dictionary
 *       tag_<n>         = the /Tag string of the resolved dictionary
 *       value_<n>       = the /Value integer of the resolved dictionary
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> PrevChainProbe facts file.pdf 6 7
 */
public final class PrevChainProbe {
    public static void main(String[] args) throws Exception {
        if (!"facts".equals(args[0])) {
            throw new IllegalArgumentException("unknown mode: " + args[0]);
        }
        String file = args[1];
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(new File(file))) {
            sb.append("pages=").append(doc.getNumberOfPages()).append("\n");
            COSBase rootRef =
                doc.getDocument().getTrailer().getItem(COSName.ROOT);
            String root = "";
            if (rootRef instanceof COSObject) {
                COSObject r = (COSObject) rootRef;
                root = r.getObjectNumber() + " " + r.getGenerationNumber();
            }
            sb.append("root=").append(root).append("\n");
            sb.append("object_count=")
              .append(doc.getDocument().getXrefTable().size()).append("\n");
            for (int i = 2; i < args.length; i++) {
                long objNum = Long.parseLong(args[i]);
                emitObject(doc, objNum, sb);
            }
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
            COSBase tag = dict.getDictionaryObject(COSName.getPDFName("Tag"));
            sb.append("tag_").append(objNum).append("=")
              .append(tag instanceof COSString ? ((COSString) tag).getString() : "")
              .append("\n");
            COSBase value = dict.getDictionaryObject(COSName.getPDFName("Value"));
            sb.append("value_").append(objNum).append("=")
              .append(value instanceof COSNumber ? ((COSNumber) value).intValue() : -1)
              .append("\n");
        }
    }
}
