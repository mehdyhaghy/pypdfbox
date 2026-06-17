import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDAttributeObject;
import org.apache.pdfbox.pdmodel.documentinterchange.markedcontent.PDMarkedContent;
import org.apache.pdfbox.pdmodel.documentinterchange.taggedpdf.PDLayoutAttributeObject;
import org.apache.pdfbox.pdmodel.documentinterchange.taggedpdf.PDListAttributeObject;
import org.apache.pdfbox.pdmodel.documentinterchange.taggedpdf.PDPrintFieldAttributeObject;
import org.apache.pdfbox.pdmodel.documentinterchange.taggedpdf.PDTableAttributeObject;
import org.apache.pdfbox.pdmodel.graphics.color.PDGamma;

/**
 * Differential fuzz probe for the TYPED-ACCESSOR VALUES on the standard
 * attribute-object subclasses (Layout / List / Table / PrintField) plus
 * {@code PDMarkedContent}, Apache PDFBox 3.0.7 (wave 1548, agent E).
 *
 * <p>The sibling probe {@code AttributeObjectFuzzProbe} (wave 1531) already
 * covered {@code create()} dispatch + {@code getOwner} / {@code isEmpty} +
 * the generic {@code PDDefaultAttributeObject} key/value surface. This probe
 * instead feeds well-/mis-typed VALUES to each subclass's typed getters and
 * projects what each getter returns on missing / wrong-type / out-of-range
 * input:
 *
 * <ul>
 *   <li>Layout: {@code getPlacement} / {@code getWritingMode} /
 *       {@code getBackgroundColor} (a {@code PDGamma}) / {@code getBorderStyle}
 *       (a String or String[]) on absent / name / wrong-type values.</li>
 *   <li>List: {@code getListNumbering} (default {@code None}) on absent /
 *       name / string / wrong-type.</li>
 *   <li>Table: {@code getRowSpan} / {@code getColSpan} (default 1) /
 *       {@code getHeaders} / {@code getScope} / {@code getSummary} on
 *       absent / wrong-type / array-with-junk.</li>
 *   <li>PrintField: {@code getRole} / {@code getCheckedState} (default
 *       {@code off}) on absent / name / string.</li>
 * </ul>
 *
 * <p>Plus a {@code PDMarkedContent} sub-corpus: {@code getTag} /
 * {@code getMCID} (default -1) / {@code getLanguage} / {@code getActualText}
 * / {@code getAlternateDescription} / {@code getExpandedForm} on a null tag,
 * null properties, and properties with present / absent / wrong-type entries,
 * plus the {@code /Artifact} dispatch to {@code PDArtifactMarkedContent}.
 *
 * <p>Driven file-based, mirroring the wave-1531 sibling: the pypdfbox test
 * builds a deterministic corpus, embeds attribute dicts as entries of a
 * {@code /FuzzAttr} COSArray and marked-content cases as entries of a
 * {@code /FuzzMC} COSArray (each {@code {Tag: <name|absent>, Props:
 * <dict|absent>}}) hung off the catalog, saves ONE {@code corpus.pdf} plus
 * a {@code manifest.txt} ({@code A:<name>} / {@code M:<name>} lines, array
 * order). This probe loads that pdf and replays both arrays.
 *
 * <p>Output grammar (one line per case, manifest order):
 * <pre>
 *   ATTR &lt;name&gt; &lt;proj&gt;
 *   MC   &lt;name&gt; &lt;proj&gt;
 * </pre>
 */
public final class AttributeAccessorFuzzProbe {

    static PrintStream out;

    static String s(String v) {
        return v == null ? "null" : v;
    }

    static String gamma(PDGamma g) {
        if (g == null) {
            return "null";
        }
        return "rgb(" + g.getR() + "," + g.getG() + "," + g.getB() + ")";
    }

    static String arr(String[] a) {
        if (a == null) {
            return "null";
        }
        return Arrays.toString(a);
    }

    static String borderStyle(Object o) {
        if (o == null) {
            return "null";
        }
        if (o instanceof String) {
            return "S:" + o;
        }
        if (o instanceof String[]) {
            return "A:" + Arrays.toString((String[]) o);
        }
        return "?:" + o.getClass().getSimpleName();
    }

    static String attrProj(PDAttributeObject ao) {
        if (ao instanceof PDLayoutAttributeObject) {
            PDLayoutAttributeObject l = (PDLayoutAttributeObject) ao;
            return "placement=" + s(l.getPlacement())
                    + " writingMode=" + s(l.getWritingMode())
                    + " bg=" + gamma(l.getBackgroundColor())
                    + " borderStyle=" + borderStyle(l.getBorderStyle());
        }
        if (ao instanceof PDListAttributeObject) {
            PDListAttributeObject l = (PDListAttributeObject) ao;
            return "listNumbering=" + s(l.getListNumbering());
        }
        if (ao instanceof PDTableAttributeObject) {
            PDTableAttributeObject t = (PDTableAttributeObject) ao;
            return "rowSpan=" + t.getRowSpan()
                    + " colSpan=" + t.getColSpan()
                    + " headers=" + arr(t.getHeaders())
                    + " scope=" + s(t.getScope())
                    + " summary=" + s(t.getSummary());
        }
        if (ao instanceof PDPrintFieldAttributeObject) {
            PDPrintFieldAttributeObject p = (PDPrintFieldAttributeObject) ao;
            return "role=" + s(p.getRole())
                    + " checked=" + s(p.getCheckedState());
        }
        return "cls=" + ao.getClass().getSimpleName();
    }

    static void runAttr(COSDictionary d, String name) {
        StringBuilder sb = new StringBuilder("ATTR ").append(name).append(' ');
        try {
            PDAttributeObject ao = PDAttributeObject.create(d);
            sb.append("cls=").append(ao.getClass().getSimpleName())
                    .append(' ').append(attrProj(ao));
        } catch (Exception e) {
            sb.append("ERR:").append(e.getClass().getSimpleName());
        }
        out.println(sb.toString());
    }

    static void runMc(COSName tag, COSDictionary props, String name) {
        StringBuilder sb = new StringBuilder("MC ").append(name).append(' ');
        try {
            PDMarkedContent mc = PDMarkedContent.create(tag, props);
            sb.append("cls=").append(mc.getClass().getSimpleName())
                    .append(" tag=").append(s(mc.getTag()))
                    .append(" mcid=").append(mc.getMCID())
                    .append(" lang=").append(s(mc.getLanguage()))
                    .append(" actual=").append(s(mc.getActualText()))
                    .append(" alt=").append(s(mc.getAlternateDescription()))
                    .append(" exp=").append(s(mc.getExpandedForm()));
        } catch (Exception e) {
            sb.append("ERR:").append(e.getClass().getSimpleName());
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
            COSArray attrArr = (COSArray) catalog.getDictionaryObject(
                    COSName.getPDFName("FuzzAttr"));
            COSArray mcArr = (COSArray) catalog.getDictionaryObject(
                    COSName.getPDFName("FuzzMC"));
            int ai = 0;
            int mi = 0;
            for (String line : cleaned) {
                if (line.startsWith("A:")) {
                    String nm = line.substring(2);
                    COSBase entry = attrArr.getObject(ai++);
                    COSDictionary d = entry instanceof COSDictionary
                            ? (COSDictionary) entry
                            : null;
                    runAttr(d, nm);
                } else if (line.startsWith("M:")) {
                    String nm = line.substring(2);
                    COSDictionary slot = (COSDictionary) mcArr.getObject(mi++);
                    COSBase tagBase =
                            slot.getDictionaryObject(COSName.getPDFName("Tag"));
                    COSName tag = tagBase instanceof COSName
                            ? (COSName) tagBase
                            : null;
                    COSBase pBase =
                            slot.getDictionaryObject(COSName.getPDFName("Props"));
                    COSDictionary props = pBase instanceof COSDictionary
                            ? (COSDictionary) pBase
                            : null;
                    runMc(tag, props, nm);
                }
            }
        }
    }
}
