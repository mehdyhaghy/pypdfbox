import java.io.File;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.graphics.optionalcontent.PDOptionalContentGroup;
import org.apache.pdfbox.pdmodel.graphics.optionalcontent.PDOptionalContentProperties;
import org.apache.pdfbox.pdmodel.graphics.optionalcontent.PDOptionalContentProperties.BaseState;

/**
 * Live oracle AUTHORING probe: build an optional-content (layers / OCG)
 * document with Apache PDFBox 3.0.7 itself and save it to disk. The companion
 * test then re-reads that genuine PDFBox-produced file with pypdfbox and
 * asserts pypdfbox's OCG accessors agree with PDFBox's own dump of the same
 * file.
 *
 * The existing {@code OcgProbe} differential builds the fixture WITH pypdfbox
 * and parses it with both libraries — that can mask a pypdfbox reader bug if
 * pypdfbox writes a structure that just happens to round-trip through its own
 * reader. This probe inverts the direction: PDFBox writes the bytes, so the
 * /OCProperties layout (the /D dict, the /ON and /OFF arrays, the indirect OCG
 * references, the /BaseState name spelling) is exactly what upstream emits, and
 * the assertion is that pypdfbox parses upstream's on-disk layout correctly.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> OcgAuthorProbe out.pdf
 *
 * The authored document is fixed (deterministic) so the test can hard-code the
 * expected dump:
 *   - BaseState = ON
 *   - OCGs: "Alpha", "Beta", "Gamma" (added in that order)
 *   - "Beta" turned OFF (setGroupEnabled("Beta", false))
 *   - "Gamma" explicitly turned ON (setGroupEnabled("Gamma", true))
 *
 * No stdout is produced; success is the saved file. The test runs OcgProbe on
 * the saved file to get PDFBox's own dump for the differential.
 */
public final class OcgAuthorProbe {
    public static void main(String[] args) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            doc.addPage(new PDPage());

            PDOptionalContentProperties ocp = new PDOptionalContentProperties();

            PDOptionalContentGroup alpha = new PDOptionalContentGroup("Alpha");
            PDOptionalContentGroup beta = new PDOptionalContentGroup("Beta");
            PDOptionalContentGroup gamma = new PDOptionalContentGroup("Gamma");
            ocp.addGroup(alpha);
            ocp.addGroup(beta);
            ocp.addGroup(gamma);

            ocp.setBaseState(BaseState.ON);
            ocp.setGroupEnabled("Beta", false);
            ocp.setGroupEnabled("Gamma", true);

            doc.getDocumentCatalog().setOCProperties(ocp);
            doc.save(new File(args[0]));
        }
    }
}
