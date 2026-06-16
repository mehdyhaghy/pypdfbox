import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.common.COSObjectable;
import org.apache.pdfbox.pdmodel.common.PDNameTreeNode;
import org.apache.pdfbox.pdmodel.common.PDNumberTreeNode;

/**
 * Differential fuzz probe for the GENERIC name-tree / number-tree LOOKUP-SWEEP
 * contract of Apache PDFBox 3.0.7 (wave 1549, agent C).
 *
 * <p>Complements the wave-1514 {@code NameNumberTreeFuzzProbe}, which projects a
 * single present/absent lookup per case. This probe instead projects a multi-key
 * lookup SWEEP across each tree (below the range, at the lower limit, a present
 * interior key, an absent interior key, at the upper limit, above the range)
 * plus the {@code /Limits} pair. It targets
 * fuzz angles the wave-1514 probe does not: a key BETWEEN limits but absent,
 * boundary-key hits, descending past a MISORDERED / OVERLAPPING intermediate
 * node (where a kid's declared {@code /Limits} cover a key it does not contain
 * but a later sibling does), and single-key leaves whose {@code /Limits} are
 * {@code lo==hi}.
 *
 * <p>As in wave 1514 both sides are driven on the SAME bytes: the pypdfbox
 * sibling ({@code tests/pdmodel/common/oracle/test_name_number_tree_fuzz_wave1549.py})
 * writes one PDF per case whose catalog carries the fuzzed tree under
 * {@code /Names /Dests} (name tree) or {@code /PageLabels} (number tree), plus a
 * {@code manifest.txt} (one case name per line, in order). This probe loads each
 * {@code <case>.pdf}, wraps the raw tree dict in a thin local node subclass and
 * projects a stable framed line; both sides read the exact same dictionary so
 * the traversal contract is directly comparable.
 *
 * <p>Line grammar (one per case, manifest order):
 * <pre>
 *   CASE &lt;name&gt; sweep=&lt;k0,k1,k2,k3,k4,k5&gt; limits=&lt;lo..hi&gt;
 * </pre>
 * where each sweep slot is {@code getValue(key)} for that probe key rendered as
 * the value string / {@code null} / {@code ERR:&lt;ExcSimpleName&gt;}.
 */
public final class NameNumberTreeLookupFuzzProbe {

    static PrintStream out;

    /** Leaf value = the decoded string of a {@code COSString}. */
    static final class _Str extends PDNameTreeNode<COSString> {
        _Str(COSDictionary dict) {
            super(dict);
        }

        @Override
        protected COSString convertCOSToPD(COSBase base) {
            return (COSString) base;
        }

        @Override
        protected PDNameTreeNode<COSString> createChildNode(COSDictionary dic) {
            return new _Str(dic);
        }
    }

    /** Thin {@link COSObjectable} wrapper so the number tree's reflective
     * {@code convertCOSToPD} resolves a value class with a COSBase ctor. */
    static final class _Wrap implements COSObjectable {
        final COSBase base;

        _Wrap(COSBase base) {
            this.base = base;
        }

        @Override
        public COSBase getCOSObject() {
            return base;
        }

        @Override
        public String toString() {
            return base instanceof COSString ? ((COSString) base).getString()
                    : base.toString();
        }
    }

    /** Number-tree node whose leaf value is the raw COSBase wrapped in _Wrap. */
    static final class _Num extends PDNumberTreeNode {
        _Num(COSDictionary dict) {
            super(dict, _Wrap.class);
        }

        @Override
        protected COSObjectable convertCOSToPD(COSBase base) {
            return new _Wrap(base);
        }

        @Override
        protected PDNumberTreeNode createChildNode(COSDictionary dic) {
            return new _Num(dic);
        }
    }

    static String nameLookup(_Str node, String key) {
        try {
            COSString v = node.getValue(key);
            return v == null ? "null" : v.getString();
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String nameLimits(_Str node) {
        String lo;
        String hi;
        try {
            lo = node.getLowerLimit();
        } catch (Exception e) {
            lo = "ERR";
        }
        try {
            hi = node.getUpperLimit();
        } catch (Exception e) {
            hi = "ERR";
        }
        return (lo == null ? "null" : lo) + ".." + (hi == null ? "null" : hi);
    }

    static String numLookup(PDNumberTreeNode node, int key) {
        try {
            Object v = node.getValue(key);
            return v == null ? "null" : v.toString();
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String numLimits(PDNumberTreeNode node) {
        String lo;
        String hi;
        try {
            Integer lower = node.getLowerLimit();
            lo = lower == null ? "null" : lower.toString();
        } catch (Exception e) {
            lo = "ERR";
        }
        try {
            Integer upper = node.getUpperLimit();
            hi = upper == null ? "null" : upper.toString();
        } catch (Exception e) {
            hi = "ERR";
        }
        return lo + ".." + hi;
    }

    /** Six name-tree probe keys: below, lower-bound, interior-present,
     * interior-absent, upper-bound, above. */
    static final String[] NAME_KEYS =
            {"AAA", "key0", "key5", "key_absent", "zzz", "zzzzz"};

    /** Six number-tree probe keys: below, lower-bound, interior-present,
     * interior-absent, upper-bound, above. */
    static final int[] NUM_KEYS = {-100, 0, 5, 7, 50, 1000};

    static COSDictionary treeDict(PDDocument doc, boolean isName) {
        PDDocumentCatalog catalog = doc.getDocumentCatalog();
        COSDictionary cat = catalog.getCOSObject();
        if (isName) {
            COSBase names = cat.getDictionaryObject(COSName.NAMES);
            if (names instanceof COSDictionary) {
                COSBase dests = ((COSDictionary) names).getDictionaryObject(COSName.DESTS);
                if (dests instanceof COSDictionary) {
                    return (COSDictionary) dests;
                }
            }
            return null;
        }
        COSBase labels = cat.getDictionaryObject(COSName.getPDFName("PageLabels"));
        return labels instanceof COSDictionary ? (COSDictionary) labels : null;
    }

    static void runCase(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');
        boolean isName = name.startsWith("name_");
        PDDocument doc = null;
        try {
            doc = Loader.loadPDF(pdf);
            COSDictionary dict = treeDict(doc, isName);
            if (dict == null) {
                sb.append("sweep=NODICT limits=NODICT");
            } else if (isName) {
                _Str node = new _Str(dict);
                sb.append("sweep=");
                for (int i = 0; i < NAME_KEYS.length; i++) {
                    if (i > 0) {
                        sb.append(',');
                    }
                    sb.append(nameLookup(node, NAME_KEYS[i]));
                }
                sb.append(" limits=").append(nameLimits(node));
            } else {
                _Num node = new _Num(dict);
                sb.append("sweep=");
                for (int i = 0; i < NUM_KEYS.length; i++) {
                    if (i > 0) {
                        sb.append(',');
                    }
                    sb.append(numLookup(node, NUM_KEYS[i]));
                }
                sb.append(" limits=").append(numLimits(node));
            }
        } catch (Exception e) {
            sb.append("open=ERR:").append(e.getClass().getSimpleName());
        } finally {
            if (doc != null) {
                try {
                    doc.close();
                } catch (Exception ignored) {
                    // best-effort close
                }
            }
        }
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        File dir = new File(args[0]);
        File manifest = new File(dir, "manifest.txt");
        String[] names =
                new String(java.nio.file.Files.readAllBytes(manifest.toPath()),
                                java.nio.charset.StandardCharsets.UTF_8)
                        .split("\n");
        Arrays.stream(names)
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .forEach(name -> runCase(dir, name));
    }
}
