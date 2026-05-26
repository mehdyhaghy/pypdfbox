import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.graphics.optionalcontent.PDOptionalContentGroup;
import org.apache.pdfbox.pdmodel.graphics.optionalcontent.PDOptionalContentProperties;

/**
 * Live oracle probe: emit Apache PDFBox's view of a PDF's optional content
 * (layers / OCG) configuration.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> OcgProbe input.pdf
 * Output (UTF-8, one item per line, canonical order):
 *   CONFIG name=<default config /Name or ""> baseState=<ON|OFF|UNCHANGED>
 *   OCG name=<ocg name> enabled=<true|false>   (one line per OCG, sorted by name)
 * When the catalog has no /OCProperties at all, the single line:
 *   NO_OCPROPERTIES
 */
public final class OcgProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDOptionalContentProperties ocp = catalog.getOCProperties();
            if (ocp == null) {
                out.println("NO_OCPROPERTIES");
                return;
            }

            // Default configuration name lives at /OCProperties /D /Name.
            // PDFBox 3.0 has no public getter for it, so read it off the COS
            // dictionary directly (mirrors pypdfbox's get_default_configuration().get_name()).
            COSDictionary ocpDict = ocp.getCOSObject();
            COSDictionary d = ocpDict.getCOSDictionary(COSName.getPDFName("D"));
            String configName = "";
            if (d != null) {
                String n = d.getString(COSName.NAME);
                if (n != null) {
                    configName = n;
                }
            }
            out.println("CONFIG name=" + configName
                    + " baseState=" + ocp.getBaseState().name());

            List<String> lines = new ArrayList<>();
            for (PDOptionalContentGroup group : ocp.getOptionalContentGroups()) {
                String name = group.getName();
                boolean enabled = ocp.isGroupEnabled(group);
                lines.add("OCG name=" + (name == null ? "" : name)
                        + " enabled=" + enabled);
            }
            Collections.sort(lines);
            for (String line : lines) {
                out.println(line);
            }
        }
    }
}
