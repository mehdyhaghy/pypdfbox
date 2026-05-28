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
 * Live oracle probe for classic xref FREE-LIST handling with
 * GENERATION-NUMBER REUSE across a {@code /Prev} chain.
 *
 * PDF 32000-1 §7.5.4 — a traditional cross-reference table records each
 * object as either in-use ({@code n}) or free ({@code f}). When an object
 * is deleted, its slot becomes a free ({@code f}) entry whose generation
 * number is incremented; a NEW object may later reuse the same object
 * NUMBER at the bumped generation. A correct parser must:
 *
 *   (1) honour the free entry from the newer revision so the OLD
 *       generation-0 object no longer resolves at its old slot, and
 *   (2) resolve the REUSED object number at its NEW generation to the
 *       object the newer revision added.
 *
 * A parser that ignores {@code f} entries (treating every table line as
 * in-use) would still surface the stale gen-0 object; one that keys the
 * pool on object number alone (dropping generation) would collide the two
 * revisions of the same number.
 *
 * Mode (one "key=value" per line on stdout; the text= line is emitted last
 * and verbatim so its newlines survive):
 *
 *   facts file.pdf num:gen [num:gen ...]
 *       pages             = page count
 *       object_count      = COSDocument.getXrefTable().size()  (pool reach)
 *       resolved_N_G      = true|false  (the num:gen key dereferences)
 *       type_N_G          = the /Type name of the resolved dictionary
 *       tag_N_G           = the /Tag string of the resolved dictionary
 *       value_N_G         = the /Value integer of the resolved dictionary
 *       text              = PDFTextStripper output, raw, last on stdout
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> XrefFreeListProbe facts file.pdf 6:0 6:1
 */
public final class XrefFreeListProbe {
    public static void main(String[] args) throws Exception {
        if (!"facts".equals(args[0])) {
            throw new IllegalArgumentException("unknown mode: " + args[0]);
        }
        String file = args[1];
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(new File(file))) {
            sb.append("pages=").append(doc.getNumberOfPages()).append("\n");
            sb.append("object_count=")
              .append(doc.getDocument().getXrefTable().size()).append("\n");
            for (int i = 2; i < args.length; i++) {
                String[] parts = args[i].split(":");
                long objNum = Long.parseLong(parts[0]);
                int gen = Integer.parseInt(parts[1]);
                emitObject(doc, objNum, gen, sb);
            }
            String text = new PDFTextStripper().getText(doc);
            sb.append("text=").append(text);
        }
        out.print(sb);
    }

    private static void emitObject(PDDocument doc, long objNum, int gen, StringBuilder sb) {
        String suffix = objNum + "_" + gen;
        COSObject obj = doc.getDocument().getObjectFromPool(new COSObjectKey(objNum, gen));
        COSBase base = (obj != null) ? obj.getObject() : null;
        sb.append("resolved_").append(suffix).append("=")
          .append(base != null).append("\n");
        if (base instanceof COSDictionary) {
            COSDictionary dict = (COSDictionary) base;
            COSBase type = dict.getDictionaryObject(COSName.TYPE);
            sb.append("type_").append(suffix).append("=")
              .append(type instanceof COSName ? ((COSName) type).getName() : "")
              .append("\n");
            COSBase tag = dict.getDictionaryObject(COSName.getPDFName("Tag"));
            sb.append("tag_").append(suffix).append("=")
              .append(tag instanceof COSString ? ((COSString) tag).getString() : "")
              .append("\n");
            COSBase value = dict.getDictionaryObject(COSName.getPDFName("Value"));
            sb.append("value_").append(suffix).append("=")
              .append(value instanceof COSNumber ? ((COSNumber) value).intValue() : -1)
              .append("\n");
        }
    }
}
