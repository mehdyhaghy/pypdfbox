import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;

/**
 * Live oracle probe: emit the FORM-level /AcroForm dictionary accessor surface
 * as Apache PDFBox parses it, one fact per line. This pins the *form* dict
 * accessors (not the per-field accessors covered by FieldProbe / FieldTree).
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> AcroFormAccessorProbe input.pdf
 *
 * The document is loaded with the null AcroForm fixup
 * (getAcroForm(null)) so PDFBox reports the dictionary exactly as parsed —
 * without AcroFormDefaultFixup generating appearances, clearing
 * /NeedAppearances, or injecting a ZaDb font into /DR. pypdfbox performs no
 * fixup on load, so the null-fixup form is the apples-to-apples reference.
 *
 * Output (UTF-8, LF-terminated), tab-separated key/value lines:
 *   FORMPRESENT\t<true|false>
 *   DA\t<getDefaultAppearance()>                 (empty string -> "")
 *   NEEDAPPEARANCES\t<getNeedAppearances()>      (true|false)
 *   DRFONTS\t<comma-joined sorted font resource names, "" when none>
 *   HASXFA\t<hasXFA()>                           (true|false)
 *   XFAPRESENT\t<getXFA() != null>               (true|false)
 *   SIGEXIST\t<isSignaturesExist()>              (true|false)
 *   APPENDONLY\t<isAppendOnly()>                 (true|false)
 *   SIGFLAGS\t<raw /SigFlags int, 0 when absent>
 *   CALCORDER\t<getCalcOrder().size()>
 *   FIELDS\t<getFields().size()>                 (top-level only)
 *   FIELDTREE\t<count of getFieldTree() iteration> (all descendants)
 *   Q\t<raw /Q int off the dict, 0 when absent>  (form-wide quadding)
 */
public final class AcroFormAccessorProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDAcroForm form = catalog.getAcroForm(null);
            StringBuilder sb = new StringBuilder();
            if (form == null) {
                sb.append("FORMPRESENT\tfalse\n");
                out.print(sb);
                return;
            }
            sb.append("FORMPRESENT\ttrue\n");
            sb.append("DA\t").append(esc(form.getDefaultAppearance())).append('\n');
            sb.append("NEEDAPPEARANCES\t").append(form.getNeedAppearances()).append('\n');
            sb.append("DRFONTS\t").append(drFonts(form)).append('\n');
            sb.append("HASXFA\t").append(form.hasXFA()).append('\n');
            sb.append("XFAPRESENT\t").append(form.getXFA() != null).append('\n');
            sb.append("SIGEXIST\t").append(form.isSignaturesExist()).append('\n');
            sb.append("APPENDONLY\t").append(form.isAppendOnly()).append('\n');
            sb.append("SIGFLAGS\t")
                .append(form.getCOSObject().getInt(COSName.getPDFName("SigFlags"), 0))
                .append('\n');
            sb.append("CALCORDER\t").append(form.getCalcOrder().size()).append('\n');
            sb.append("FIELDS\t").append(form.getFields().size()).append('\n');
            int treeCount = 0;
            for (PDField ignored : form.getFieldTree()) {
                treeCount++;
            }
            sb.append("FIELDTREE\t").append(treeCount).append('\n');
            sb.append("Q\t")
                .append(form.getCOSObject().getInt(COSName.getPDFName("Q"), 0))
                .append('\n');
            out.print(sb);
        }
    }

    /** Comma-joined, sorted resource names of the /DR fonts ("" when none). */
    private static String drFonts(PDAcroForm form) {
        PDResources dr = form.getDefaultResources();
        if (dr == null) {
            return "";
        }
        java.util.List<String> names = new java.util.ArrayList<>();
        for (COSName fontName : dr.getFontNames()) {
            try {
                PDFont font = dr.getFont(fontName);
                if (font != null) {
                    names.add(fontName.getName());
                }
            } catch (Exception e) {
                names.add(fontName.getName());
            }
        }
        java.util.Collections.sort(names);
        return String.join(",", names);
    }

    private static String esc(String s) {
        if (s == null) {
            return "";
        }
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")
                .replace("\t", "\\t");
    }
}
