import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.documentinterchange.markedcontent.PDPropertyList;
import org.apache.pdfbox.pdmodel.graphics.optionalcontent.PDOptionalContentGroup;
import org.apache.pdfbox.pdmodel.graphics.optionalcontent.PDOptionalContentMembershipDictionary;

/**
 * Live oracle probe: emit Apache PDFBox's view of an optional content
 * membership dictionary (OCMD) stored in the first page's
 * /Resources /Properties under the resource name given by args[1].
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> OcmdProbe input.pdf <resourceName>
 * Output (UTF-8, canonical order):
 *   POLICY=<AllOn|AnyOn|AnyOff|AllOff>
 *   OCG name=<ocg name>   (one line per OCG referenced by /OCGs, sorted)
 * When the named property list is absent or not an OCMD:
 *   NOT_OCMD
 */
public final class OcmdProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDPage page = doc.getPage(0);
            PDResources res = page.getResources();
            COSName name = COSName.getPDFName(args[1]);
            PDPropertyList pl = res == null ? null : res.getProperties(name);
            if (!(pl instanceof PDOptionalContentMembershipDictionary)) {
                out.println("NOT_OCMD");
                return;
            }
            PDOptionalContentMembershipDictionary ocmd =
                    (PDOptionalContentMembershipDictionary) pl;
            out.println("POLICY=" + ocmd.getVisibilityPolicy().getName());
            List<String> lines = new ArrayList<>();
            for (PDPropertyList g : ocmd.getOCGs()) {
                if (g instanceof PDOptionalContentGroup) {
                    String n = ((PDOptionalContentGroup) g).getName();
                    lines.add("OCG name=" + (n == null ? "" : n));
                }
            }
            Collections.sort(lines);
            for (String line : lines) {
                out.println(line);
            }
        }
    }
}
