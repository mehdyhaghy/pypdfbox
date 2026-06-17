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
 * Live oracle probe for PDF cross-reference chains that mix an xref STREAM
 * (newest revision, PDF 1.5+) with a CLASSIC ``xref...trailer`` (older
 * revision) via the stream dictionary's ``/Prev`` pointer.
 *
 * PDF 32000-1 §7.5.8.3 states that an xref stream's ``/Prev`` may point at
 * EITHER another xref stream OR a traditional xref+trailer of an earlier
 * revision. A parser that stops at the stream (never following /Prev into a
 * classic table) loses every object that lives only in the earlier revision.
 *
 * Mode (one "key=value" per line on stdout; the text= line is emitted last and
 * verbatim so its newlines are preserved):
 *
 *   facts file.pdf objnum [objnum2 ...]
 *       pages           = page count
 *       object_count    = COSDocument.getObjects().size()  (pool reach)
 *       text            = PDFTextStripper output, raw, last on stdout
 *       resolved_<n>    = true|false  (object dereferences to non-null)
 *       type_<n>        = the /Type name of the resolved dictionary
 *       tag_<n>         = the /Tag string of the resolved dictionary
 *       value_<n>       = the /Value integer of the resolved dictionary
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> XrefChainProbe facts file.pdf 5 6
 */
public final class XrefChainProbe {
    public static void main(String[] args) throws Exception {
        if (!"facts".equals(args[0])) {
            throw new IllegalArgumentException("unknown mode: " + args[0]);
        }
        String file = args[1];
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(new File(file))) {
            sb.append("pages=").append(doc.getNumberOfPages()).append("\n");
            sb.append("object_count=").append(doc.getDocument().getXrefTable().size()).append("\n");
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
