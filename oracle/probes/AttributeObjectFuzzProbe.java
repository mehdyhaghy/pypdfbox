import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDAttributeObject;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDDefaultAttributeObject;

/**
 * Differential fuzz probe for
 * {@code PDAttributeObject.create(COSDictionary)} dispatch + the
 * {@code getOwner} / {@code isEmpty} surface and
 * {@code PDDefaultAttributeObject} generic key/value access, Apache PDFBox
 * 3.0.7 (wave 1531, agent D).
 *
 * The create() factory dispatches on {@code getNameAsString(/O)} — which
 * resolves a /O stored as either a COSName OR a COSString — to a typed
 * subclass (PDLayout / PDList / PDPrintField / PDTable / PDExportFormat
 * (XML-1.00 / HTML-3.2 / HTML-4.01 / OEB-1.00 / RTF-1.05 / CSS-1.00 /
 * CSS-2.00) / PDUser) and otherwise falls back to
 * PDDefaultAttributeObject. This probe targets the MALFORMED / edge-case
 * subset: /O missing / unknown / wrong-type (int/array/dict/bool/real),
 * /O as name vs string, each known owner value, empty dict, indirect-ref
 * /O, and (for the default wrapper) generic attribute access for present
 * vs absent keys including nested values.
 *
 * Driven file-based: the pypdfbox sibling
 * (tests/pdmodel/documentinterchange/logicalstructure/oracle/test_attribute_object_fuzz_wave1531.py)
 * builds a deterministic corpus of dictionaries, embeds them as entries of
 * a non-standard {@code /FuzzAttrObjs} COSArray hung off the document
 * catalog, and saves ONE pdf ({@code corpus.pdf}) plus a
 * {@code manifest.txt} (one case name per line, array order). This probe
 * loads that pdf, walks the array, and for each slot feeds the raw
 * COSDictionary to create() and projects a stable framed line. Both sides
 * read the exact same bytes on disk.
 *
 * Output grammar (one line per case, manifest order):
 *   CASE &lt;name&gt; class=&lt;simpleName|null&gt; owner=&lt;getOwner|null&gt; empty=&lt;true|false&gt; attrs=&lt;proj&gt;
 *
 * class = create()'s runtime class simple name, or ERR:&lt;Exc&gt;.
 * owner = getOwner() (getNameAsString(/O)), or "null".
 * empty = isEmpty().
 * attrs = for a PDDefaultAttributeObject, the attribute-name list and each
 *         value's COS shape ("name:shape" comma-joined, fixed dictionary
 *         order); "-" for a typed subclass; "ERR:&lt;Exc&gt;" on failure.
 */
public final class AttributeObjectFuzzProbe {

    static PrintStream out;

    static String shape(COSBase b) {
        if (b == null) {
            return "null";
        }
        if (b instanceof COSStream) {
            return "stream";
        }
        if (b instanceof COSDictionary) {
            return "dict";
        }
        if (b instanceof COSArray) {
            return "arr" + ((COSArray) b).size();
        }
        if (b instanceof COSName) {
            return "name";
        }
        if (b instanceof COSString) {
            return "str";
        }
        if (b instanceof COSInteger) {
            return "int";
        }
        if (b instanceof COSFloat) {
            return "real";
        }
        if (b instanceof COSBoolean) {
            return "bool";
        }
        return "other";
    }

    static String attrsProj(PDAttributeObject ao) {
        if (!(ao instanceof PDDefaultAttributeObject)) {
            return "-";
        }
        PDDefaultAttributeObject d = (PDDefaultAttributeObject) ao;
        COSDictionary cos = d.getCOSObject();
        StringBuilder sb = new StringBuilder();
        boolean first = true;
        for (COSName key : cos.keySet()) {
            if (COSName.O.equals(key)) {
                continue;
            }
            if (!first) {
                sb.append(',');
            }
            first = false;
            sb.append(key.getName()).append(':')
                    .append(shape(d.getAttributeValue(key.getName())));
        }
        if (first) {
            return "{}";
        }
        return sb.toString();
    }

    static void runCase(COSDictionary d, String name) {
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');
        try {
            PDAttributeObject ao = PDAttributeObject.create(d);
            String cls = ao == null ? "null" : ao.getClass().getSimpleName();
            String owner = ao == null ? "null" : ao.getOwner();
            if (owner == null) {
                owner = "null";
            }
            boolean empty = ao != null && ao.isEmpty();
            sb.append("class=").append(cls);
            sb.append(" owner=").append(owner);
            sb.append(" empty=").append(empty);
            sb.append(" attrs=").append(ao == null ? "-" : attrsProj(ao));
        } catch (Exception e) {
            sb.append("class=ERR:").append(e.getClass().getSimpleName());
            sb.append(" owner=ERR empty=ERR attrs=ERR");
        }
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        File dir = new File(args[0]);
        File pdf = new File(dir, "corpus.pdf");
        File manifest = new File(dir, "manifest.txt");
        String[] names =
                new String(java.nio.file.Files.readAllBytes(manifest.toPath()),
                                java.nio.charset.StandardCharsets.UTF_8)
                        .split("\n");
        String[] cleaned =
                Arrays.stream(names).map(String::trim).filter(s -> !s.isEmpty())
                        .toArray(String[]::new);
        try (PDDocument doc = Loader.loadPDF(pdf)) {
            COSDictionary catalog = doc.getDocumentCatalog().getCOSObject();
            COSBase fz =
                    catalog.getDictionaryObject(COSName.getPDFName("FuzzAttrObjs"));
            COSArray arr = (COSArray) fz;
            for (int i = 0; i < cleaned.length; i++) {
                COSBase entry = arr.getObject(i);
                COSDictionary d = entry instanceof COSDictionary
                        ? (COSDictionary) entry
                        : null;
                runCase(d, cleaned[i]);
            }
        }
    }
}
