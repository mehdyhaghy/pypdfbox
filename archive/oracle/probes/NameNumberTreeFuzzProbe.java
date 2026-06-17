import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
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
 * Differential fuzz probe for the GENERIC name-tree / number-tree traversal +
 * lookup contract of Apache PDFBox 3.0.7 (wave 1514, agent E).
 *
 * <p>Targets {@link PDNameTreeNode} and {@link PDNumberTreeNode} directly (not
 * a value-typed subclass) so the projection isolates the base-class traversal
 * behaviour from any leaf-value-construction leniency. A thin local subclass on
 * each side converts a leaf {@code COSString} to its Java string ({@code _Str})
 * and a leaf {@code COSInteger} value position is left as the raw {@code COSBase}
 * ({@code _Num}); the pypdfbox sibling mirrors both subclasses.
 *
 * <p>The corpus is file-driven: the pypdfbox sibling
 * ({@code tests/pdmodel/common/oracle/test_name_number_tree_fuzz_wave1514.py})
 * writes one PDF per case whose catalog carries the fuzzed tree under
 * {@code /Names /Dests} (name tree) or {@code /PageLabels} (number tree), plus a
 * {@code manifest.txt} (one case name per line, in order). This probe loads each
 * {@code <case>.pdf}, reaches the catalog COS, wraps the raw tree dict in the
 * matching local node subclass and projects a stable framed line. Both sides
 * read the exact same bytes, so the traversal contract is directly comparable.
 *
 * <p>Covered malformations: {@code /Kids}-vs-{@code /Names}/{@code /Nums} (leaf
 * vs intermediate); odd-length value array (key without value); wrong key type
 * (non-string name key / non-int number key); unsorted keys; {@code /Limits}
 * missing / wrong arity / inverted (lo&gt;hi) / wrong type; {@code /Kids}
 * non-array / containing a non-dict / deeply nested; lookup of a present key, an
 * absent key, and a key outside {@code /Limits}.
 *
 * <p>Line grammar (one per case, manifest order):
 * <pre>
 *   CASE &lt;name&gt; names=&lt;count|null|ERR&gt; kids=&lt;count|null|ERR&gt;
 *        lookup_hit=&lt;v|null|ERR&gt; lookup_miss=&lt;null|ERR&gt; limits=&lt;lo..hi&gt;
 * </pre>
 *
 * <p>{@code names} is the size of {@code getNames()}/{@code getNumbers()}
 * (non-recursive, this node's own leaf array), {@code null} when that returns
 * null, {@code ERR:&lt;ExcSimpleName&gt;} when it throws. {@code kids} is the
 * size of {@code getKids()} ({@code null} when absent). {@code lookup_hit} is
 * {@code getValue(presentKey)}, {@code lookup_miss} is
 * {@code getValue(absentKey)}. {@code limits} is
 * {@code getLowerLimit()..getUpperLimit()}.
 */
public final class NameNumberTreeFuzzProbe {

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

    static String nameTreeNames(_Str node) {
        try {
            Map<String, COSString> names = node.getNames();
            return names == null ? "null" : Integer.toString(names.size());
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String nameTreeKids(_Str node) {
        try {
            List<PDNameTreeNode<COSString>> kids = node.getKids();
            return kids == null ? "null" : Integer.toString(kids.size());
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String nameTreeLookup(_Str node, String key) {
        try {
            COSString v = node.getValue(key);
            return v == null ? "null" : v.getString();
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String nameTreeLimits(_Str node) {
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

    static String numTreeNames(PDNumberTreeNode node) {
        try {
            Map<Integer, COSObjectable> nums = node.getNumbers();
            return nums == null ? "null" : Integer.toString(nums.size());
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String numTreeKids(PDNumberTreeNode node) {
        try {
            List<PDNumberTreeNode> kids = node.getKids();
            return kids == null ? "null" : Integer.toString(kids.size());
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String numTreeLookup(PDNumberTreeNode node, int key) {
        try {
            Object v = node.getValue(key);
            return v == null ? "null" : valueToString(v);
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String valueToString(Object v) {
        return v.toString();
    }

    static String numTreeLimits(PDNumberTreeNode node) {
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
                sb.append("names=NODICT kids=NODICT lookup_hit=NODICT ")
                        .append("lookup_miss=NODICT limits=NODICT");
            } else if (isName) {
                _Str node = new _Str(dict);
                sb.append("names=").append(nameTreeNames(node));
                sb.append(" kids=").append(nameTreeKids(node));
                sb.append(" lookup_hit=").append(nameTreeLookup(node, "key1"));
                sb.append(" lookup_miss=").append(nameTreeLookup(node, "zzzmiss"));
                sb.append(" limits=").append(nameTreeLimits(node));
            } else {
                _Num node = new _Num(dict);
                sb.append("names=").append(numTreeNames(node));
                sb.append(" kids=").append(numTreeKids(node));
                sb.append(" lookup_hit=").append(numTreeLookup(node, 1));
                sb.append(" lookup_miss=").append(numTreeLookup(node, 999));
                sb.append(" limits=").append(numTreeLimits(node));
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
