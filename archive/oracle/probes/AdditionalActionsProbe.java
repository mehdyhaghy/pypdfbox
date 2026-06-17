import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.interactive.action.PDAction;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionJavaScript;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionURI;
import org.apache.pdfbox.pdmodel.interactive.action.PDAnnotationAdditionalActions;
import org.apache.pdfbox.pdmodel.interactive.action.PDDocumentCatalogAdditionalActions;
import org.apache.pdfbox.pdmodel.interactive.action.PDFormFieldAdditionalActions;
import org.apache.pdfbox.pdmodel.interactive.action.PDPageAdditionalActions;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationWidget;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;
import org.apache.pdfbox.pdmodel.interactive.form.PDTerminalField;

/**
 * Live oracle probe: enumerate every additional-actions (/AA) container in a
 * PDF and the triggers present on each, with each trigger's action subtype
 * (and JS source / URI where applicable).
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> AdditionalActionsProbe input.pdf
 * Output: canonical sorted lines, UTF-8, to stdout. One line per present
 * trigger:
 *   <container> <trigger> <subtype> [js=<code>] [uri=<uri>]
 * where <container> is one of: annot field page catalog.
 */
public final class AdditionalActionsProbe {

    private static String esc(String s) {
        if (s == null) {
            return "none";
        }
        return s.replace("\\", "\\\\")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }

    private static String describe(String container, String trigger, PDAction action) {
        if (action == null) {
            return null;
        }
        String sub = action.getSubType();
        StringBuilder sb = new StringBuilder();
        sb.append(container).append(' ').append(trigger).append(' ')
          .append(sub == null ? "none" : sub);
        if (action instanceof PDActionJavaScript) {
            sb.append(" js=").append(esc(((PDActionJavaScript) action).getAction()));
        } else if (action instanceof PDActionURI) {
            sb.append(" uri=").append(esc(((PDActionURI) action).getURI()));
        }
        return sb.toString();
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        List<String> lines = new ArrayList<>();
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();

            // ---- catalog /AA ----
            COSDictionary catAa =
                catalog.getCOSObject().getCOSDictionary(COSName.AA);
            if (catAa != null) {
                PDDocumentCatalogAdditionalActions aa =
                    new PDDocumentCatalogAdditionalActions(catAa);
                add(lines, "catalog", "WC", aa.getWC());
                add(lines, "catalog", "WS", aa.getWS());
                add(lines, "catalog", "DS", aa.getDS());
                add(lines, "catalog", "WP", aa.getWP());
                add(lines, "catalog", "DP", aa.getDP());
            }

            // ---- page /AA + annotation /AA ----
            for (PDPage page : doc.getPages()) {
                COSDictionary pageAa =
                    page.getCOSObject().getCOSDictionary(COSName.AA);
                if (pageAa != null) {
                    PDPageAdditionalActions aa = new PDPageAdditionalActions(pageAa);
                    add(lines, "page", "O", aa.getO());
                    add(lines, "page", "C", aa.getC());
                }
                for (PDAnnotation annot : page.getAnnotations()) {
                    COSDictionary annotAa =
                        annot.getCOSObject().getCOSDictionary(COSName.AA);
                    if (annotAa == null) {
                        continue;
                    }
                    PDAnnotationAdditionalActions aa =
                        new PDAnnotationAdditionalActions(annotAa);
                    add(lines, "annot", "E", aa.getE());
                    add(lines, "annot", "X", aa.getX());
                    add(lines, "annot", "D", aa.getD());
                    add(lines, "annot", "U", aa.getU());
                    add(lines, "annot", "Fo", aa.getFo());
                    add(lines, "annot", "Bl", aa.getBl());
                    add(lines, "annot", "PO", aa.getPO());
                    add(lines, "annot", "PC", aa.getPC());
                    add(lines, "annot", "PV", aa.getPV());
                    add(lines, "annot", "PI", aa.getPI());
                }
            }

            // ---- field /AA ----
            PDAcroForm form = catalog.getAcroForm();
            if (form != null) {
                for (PDField field : form.getFieldTree()) {
                    if (!(field instanceof PDTerminalField)) {
                        continue;
                    }
                    PDFormFieldAdditionalActions aa =
                        ((PDTerminalField) field).getActions();
                    if (aa == null) {
                        continue;
                    }
                    add(lines, "field", "K", aa.getK());
                    add(lines, "field", "F", aa.getF());
                    add(lines, "field", "V", aa.getV());
                    add(lines, "field", "C", aa.getC());
                }
            }
        }
        java.util.Collections.sort(lines);
        for (String line : lines) {
            out.println(line);
        }
    }

    private static void add(List<String> lines, String container, String trigger,
                            PDAction action) {
        String s = describe(container, trigger, action);
        if (s != null) {
            lines.add(s);
        }
    }
}
