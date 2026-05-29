import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.interactive.action.PDAction;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionGoTo;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionJavaScript;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionNamed;
import org.apache.pdfbox.pdmodel.interactive.action.PDDocumentCatalogAdditionalActions;
import org.apache.pdfbox.pdmodel.interactive.action.PDPageAdditionalActions;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitDestination;

/**
 * Live oracle probe for the additional-actions (/AA) accessor surface on
 * {@link PDPageAdditionalActions} (page /O open + /C close) and
 * {@link PDDocumentCatalogAdditionalActions} (catalog /WS will-save +
 * /DP did-print).
 *
 * Apache PDFBox AUTHORS the file: a page /AA with /O = JavaScript and
 * /C = GoTo, and a catalog /AA with /WS = JavaScript and /DP = Named. It
 * saves the document to args[0], reloads it, and emits — as one flat JSON
 * object — each trigger's presence, dispatched action subtype, and one
 * salient field (JS source for JavaScript, /N name for Named, destination
 * presence for GoTo). pypdfbox reads the SAME PDFBox-authored bytes and must
 * reproduce the identical JSON, proving its /AA reader + PDActionFactory
 * dispatch matches authoritative PDFBox output.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> AaTriggerJsonProbe out.pdf
 * Output: one JSON object, UTF-8, to stdout.
 */
public final class AaTriggerJsonProbe {

    private static String esc(String s) {
        if (s == null) {
            return null;
        }
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '\\': sb.append("\\\\"); break;
                case '"':  sb.append("\\\""); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default:   sb.append(c);
            }
        }
        return sb.toString();
    }

    private static String jstr(String s) {
        return s == null ? "null" : "\"" + esc(s) + "\"";
    }

    private static String jbool(boolean b) {
        return b ? "true" : "false";
    }

    /** Salient field for one trigger's action, or "null" if absent. */
    private static String salient(PDAction action) {
        if (action == null) {
            return "null";
        }
        if (action instanceof PDActionJavaScript) {
            return jstr(((PDActionJavaScript) action).getAction());
        }
        if (action instanceof PDActionNamed) {
            return jstr(((PDActionNamed) action).getN());
        }
        if (action instanceof PDActionGoTo) {
            // Encode whether a /D destination is present, not its value, so
            // the comparison stays layout-independent.
            try {
                return jbool(((PDActionGoTo) action).getDestination() != null);
            } catch (Exception e) {
                return jbool(false);
            }
        }
        return "null";
    }

    private static void emit(StringBuilder sb, String trigger, PDAction action,
                             boolean first) {
        if (!first) {
            sb.append(',');
        }
        sb.append(jstr(trigger)).append(":{");
        sb.append("\"present\":").append(jbool(action != null));
        sb.append(",\"subtype\":")
          .append(action == null ? "null" : jstr(action.getSubType()));
        sb.append(",\"salient\":").append(salient(action));
        sb.append('}');
    }

    private static void build(String path) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);

            // page /AA: /O = JavaScript, /C = GoTo (Fit dest on same page).
            PDPageAdditionalActions pageAa = new PDPageAdditionalActions();
            pageAa.setO(new PDActionJavaScript("app.alert('page open');"));
            PDActionGoTo close = new PDActionGoTo();
            PDPageFitDestination closeDest = new PDPageFitDestination();
            closeDest.setPage(page);
            close.setDestination(closeDest);
            pageAa.setC(close);
            page.setActions(pageAa);

            // catalog /AA: /WS = JavaScript, /DP = Named.
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDDocumentCatalogAdditionalActions catAa =
                new PDDocumentCatalogAdditionalActions();
            catAa.setWS(new PDActionJavaScript("app.alert('will save');"));
            PDActionNamed didPrint = new PDActionNamed();
            didPrint.setN("NextPage");
            catAa.setDP(didPrint);
            catalog.setActions(catAa);

            doc.save(path);
        }
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        build(args[0]);

        StringBuilder sb = new StringBuilder();
        sb.append('{');
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();

            PDPage page = doc.getPage(0);
            PDPageAdditionalActions pageAa = page.getActions();
            emit(sb, "page.O", pageAa == null ? null : pageAa.getO(), true);
            emit(sb, "page.C", pageAa == null ? null : pageAa.getC(), false);

            PDDocumentCatalogAdditionalActions catAa = catalog.getActions();
            emit(sb, "catalog.WS", catAa == null ? null : catAa.getWS(), false);
            emit(sb, "catalog.WC", catAa == null ? null : catAa.getWC(), false);
            emit(sb, "catalog.WP", catAa == null ? null : catAa.getWP(), false);
            emit(sb, "catalog.DS", catAa == null ? null : catAa.getDS(), false);
            emit(sb, "catalog.DP", catAa == null ? null : catAa.getDP(), false);
        }
        sb.append('}');
        out.println(sb.toString());
    }
}
