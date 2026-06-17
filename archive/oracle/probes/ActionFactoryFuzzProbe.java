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
import org.apache.pdfbox.pdmodel.interactive.action.PDAction;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionFactory;

/**
 * Differential fuzz probe for {@code PDActionFactory.createAction(COSDictionary)}
 * dispatch + per-subtype action-dictionary parsing leniency, Apache PDFBox 3.0.7
 * (wave 1513, agent C).
 *
 * Complements the existing well-formed action oracle suite (ActionProbe,
 * ActionAccessorProbe, ActionDestTypeProbe, ActionHideTargetProbe,
 * ActionNextChainProbe, AdditionalActionsProbe) — none of which exercise the
 * MALFORMED / edge-case action-dictionary subset this probe targets:
 *   - {@code /S} missing / unknown / mistyped (string instead of name).
 *   - per-subtype payloads with the wrong COS type or missing entirely
 *     (URI as name/string/missing; GoTo /D as array/name/string/dict;
 *     GoToR/Launch /F as string/dict/missing; JS as string/stream/missing;
 *     Named /N standard + non-standard; Launch /Win dict; Submit/Reset/Hide
 *     /Fields as array/single/missing; Hide /T as string/array/dict).
 *   - {@code /Next} chains (single dict, array, nested, with unknown members).
 *
 * Driven file-based: the pypdfbox sibling
 * (tests/pdmodel/interactive/action/oracle/test_action_factory_fuzz_wave1513.py)
 * builds a deterministic corpus of action dictionaries, embeds them as entries
 * of a non-standard {@code /FuzzActions} COSArray hung off the document catalog,
 * and saves ONE pdf ({@code corpus.pdf}) plus a {@code manifest.txt} (one case
 * name per line, in array order). This probe loads that single pdf, walks the
 * {@code /FuzzActions} array, and for each slot feeds the raw COSDictionary to
 * {@code PDActionFactory.createAction} and projects a stable framed line. Both
 * sides read the exact same bytes on disk, so the parse contract is directly
 * comparable.
 *
 * Output grammar (one line per case, manifest order):
 *   CASE &lt;name&gt; class=&lt;simpleName|null&gt; sub=&lt;S-value|null&gt; payload=&lt;proj|ERR:&lt;Exc&gt;&gt;
 *
 * class   = createAction's runtime class simple name, or "null" when the
 *           factory returns null (unknown / absent /S).
 * sub     = the /S name resolved via getNameAsString, or "null".
 * payload = a per-subtype, COS-shape projection (see projectPayload). Each
 *           projected key is rendered "key:&lt;shape&gt;" where shape is one of
 *           str|name|dict|arrN|int|real|bool|stream|null|other — the COS type
 *           the entry resolves to (null = key absent). Keys are emitted in a
 *           fixed per-subtype order, comma-joined. "ERR:&lt;ExcSimpleName&gt;" if
 *           projection threw. "-" when the factory returned null.
 *
 * The shape projection deliberately works at the raw-COS level (identical
 * getDictionaryObject semantics on both libraries) rather than through the
 * accessor methods, whose text-decoding details (e.g. getURI's UTF-8/UTF-16
 * tolerance vs upstream getString) are a separate accessor-level concern out of
 * scope for a factory-dispatch + parse-leniency fuzz.
 */
public final class ActionFactoryFuzzProbe {

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

    static String key(COSDictionary d, String name) {
        return name + ":" + shape(d.getDictionaryObject(COSName.getPDFName(name)));
    }

    static String nextProj(COSDictionary d) {
        COSBase nxt = d.getDictionaryObject(COSName.getPDFName("Next"));
        return "Next:" + shape(nxt);
    }

    /** Per-subtype, fixed-order COS-shape projection of the payload keys. */
    static String projectPayload(PDAction action, COSDictionary d, String sub) {
        if (action == null) {
            return "-";
        }
        StringBuilder p = new StringBuilder();
        if ("URI".equals(sub)) {
            p.append(key(d, "URI")).append(',').append(key(d, "IsMap"));
        } else if ("GoTo".equals(sub)) {
            p.append(key(d, "D"));
        } else if ("GoToR".equals(sub)) {
            p.append(key(d, "F")).append(',').append(key(d, "D"))
                    .append(',').append(key(d, "NewWindow"));
        } else if ("GoToE".equals(sub)) {
            p.append(key(d, "F")).append(',').append(key(d, "D"))
                    .append(',').append(key(d, "T"));
        } else if ("Launch".equals(sub)) {
            p.append(key(d, "F")).append(',').append(key(d, "Win"))
                    .append(',').append(key(d, "NewWindow"));
        } else if ("Named".equals(sub)) {
            p.append(key(d, "N"));
        } else if ("JavaScript".equals(sub)) {
            p.append(key(d, "JS"));
        } else if ("SubmitForm".equals(sub)) {
            p.append(key(d, "F")).append(',').append(key(d, "Fields"))
                    .append(',').append(key(d, "Flags"));
        } else if ("ResetForm".equals(sub)) {
            p.append(key(d, "Fields")).append(',').append(key(d, "Flags"));
        } else if ("Hide".equals(sub)) {
            p.append(key(d, "T")).append(',').append(key(d, "H"));
        } else if ("Thread".equals(sub)) {
            p.append(key(d, "F")).append(',').append(key(d, "D"))
                    .append(',').append(key(d, "B"));
        } else if ("Sound".equals(sub)) {
            p.append(key(d, "Sound"));
        } else if ("Movie".equals(sub)) {
            p.append(key(d, "T")).append(',').append(key(d, "Operation"));
        } else if ("ImportData".equals(sub)) {
            p.append(key(d, "F"));
        } else if ("SetOCGState".equals(sub)) {
            p.append(key(d, "State")).append(',').append(key(d, "PreserveRB"));
        } else {
            // Subtypes without a dedicated factory case still get a generic
            // entry-count + /Next projection so any dispatch surprise shows up.
            p.append("entries:").append(d.size());
        }
        p.append(',').append(nextProj(d));
        return p.toString();
    }

    static void runCase(COSDictionary d, String name) {
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');
        try {
            PDAction action = PDActionFactory.createAction(d);
            String cls = action == null ? "null" : action.getClass().getSimpleName();
            String sub = d == null ? "null" : d.getNameAsString(COSName.S);
            if (sub == null) {
                sub = "null";
            }
            String payload = projectPayload(action, d, d == null ? null : sub);
            sb.append("class=").append(cls);
            sb.append(" sub=").append(sub);
            sb.append(" payload=").append(payload);
        } catch (Exception e) {
            sb.append("class=ERR sub=ERR payload=ERR:")
                    .append(e.getClass().getSimpleName());
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
            COSBase fz = catalog.getDictionaryObject(COSName.getPDFName("FuzzActions"));
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
