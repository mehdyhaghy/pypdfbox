import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageTree;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;

/**
 * Differential fuzz probe for {@link PDPageTree} traversal combined with
 * per-page INHERITED attribute resolution, Apache PDFBox 3.0.7 (wave 1546).
 *
 * <p>Complements two existing probes without overlapping them:
 * <ul>
 *   <li>{@code PageTreeCycleFuzzProbe} (wave 1520) fuzzes traversal of
 *       cyclic / lying-{@code /Count} / malformed-kid trees but projects only
 *       a {@code ProbeID:Type} cell per page — it never resolves the inherited
 *       {@code /MediaBox} {@code /CropBox} {@code /Rotate} {@code /Resources}
 *       of the located pages;</li>
 *   <li>{@code PageInheritanceFuzzProbe} (wave 1515) resolves those four
 *       attributes but for a SINGLE round-tripped page loaded from PDF bytes —
 *       it never exercises multi-page sweeps, nearest-wins across several
 *       {@code /Pages} levels, lying {@code /Count} during {@code get(i)}
 *       descent, or {@code /Kids} given as a direct dict instead of an array.</li>
 * </ul>
 *
 * <p>This probe builds in-memory COS page trees by hand (like the cycle probe),
 * wraps each in a {@link PDPageTree}, and for every reachable page projects the
 * resolved inheritable attributes. The grammar per case is:
 *
 * <pre>
 *   CASE &lt;id&gt; count=&lt;n&gt; iter=&lt;cell;cell;...|-&gt;
 *       get=&lt;cell|ERR&gt;,&lt;cell|ERR&gt;,&lt;cell|ERR&gt;
 * </pre>
 *
 * where each page cell is
 * {@code <probeid>|mb=<rect>|cb=<rect>|rot=<n>|res=<present|null>} and an error
 * is one of INDEX / STATE / STACK / ERR:Name. Rectangles render as
 * {@code llx,lly,urx,ury} via {@link #fmt(float)} so integral coordinates lose
 * the trailing {@code .0} and both runtimes agree byte-for-byte.
 */
public final class PageTreeInheritFuzzProbe {
    private static final COSName PROBE_ID = COSName.getPDFName("ProbeID");
    private static final int GET_SWEEP = 3;

    private static COSDictionary pages(int count) {
        COSDictionary node = new COSDictionary();
        node.setItem(COSName.TYPE, COSName.PAGES);
        node.setItem(COSName.KIDS, new COSArray());
        node.setInt(COSName.COUNT, count);
        return node;
    }

    private static COSArray kids(COSDictionary node) {
        return (COSArray) node.getDictionaryObject(COSName.KIDS);
    }

    private static COSDictionary page(String id) {
        COSDictionary leaf = new COSDictionary();
        leaf.setItem(COSName.TYPE, COSName.PAGE);
        leaf.setString(PROBE_ID, id);
        return leaf;
    }

    /** Add {@code kid} under {@code parent} and wire its {@code /Parent}. */
    private static COSDictionary attach(COSDictionary parent, COSDictionary kid) {
        kids(parent).add(kid);
        kid.setItem(COSName.PARENT, parent);
        return kid;
    }

    private static COSArray rect(double a, double b, double c, double d) {
        COSArray r = new COSArray();
        r.add(new org.apache.pdfbox.cos.COSFloat((float) a));
        r.add(new org.apache.pdfbox.cos.COSFloat((float) b));
        r.add(new org.apache.pdfbox.cos.COSFloat((float) c));
        r.add(new org.apache.pdfbox.cos.COSFloat((float) d));
        return r;
    }

    private static void setBox(COSDictionary node, COSName key, COSArray box) {
        node.setItem(key, box);
    }

    private static COSDictionary build(String id) {
        COSDictionary root = pages(1);
        switch (id) {
            case "I01": {
                // Two pages, MediaBox + Rotate + Resources on root (inherited).
                root.setInt(COSName.COUNT, 2);
                setBox(root, COSName.MEDIA_BOX, rect(0, 0, 100, 200));
                root.setInt(COSName.ROTATE, 90);
                root.setItem(COSName.RESOURCES, new COSDictionary());
                attach(root, page("a"));
                attach(root, page("b"));
                return root;
            }
            case "I02": {
                // Nearest-wins: leaf overrides inherited MediaBox + Rotate.
                setBox(root, COSName.MEDIA_BOX, rect(0, 0, 100, 200));
                root.setInt(COSName.ROTATE, 90);
                COSDictionary leaf = page("a");
                setBox(leaf, COSName.MEDIA_BOX, rect(0, 0, 300, 400));
                leaf.setInt(COSName.ROTATE, 180);
                attach(root, leaf);
                return root;
            }
            case "I03": {
                // Deep nest: attribute set at top, page at depth 3 inherits it.
                setBox(root, COSName.MEDIA_BOX, rect(0, 0, 50, 60));
                root.setInt(COSName.ROTATE, 270);
                COSDictionary mid = attach(root, pages(1));
                COSDictionary deep = attach(mid, pages(1));
                attach(deep, page("deep"));
                return root;
            }
            case "I04": {
                // Nearest-wins across levels: mid overrides root MediaBox.
                root.setInt(COSName.COUNT, 1);
                setBox(root, COSName.MEDIA_BOX, rect(0, 0, 10, 10));
                COSDictionary mid = attach(root, pages(1));
                setBox(mid, COSName.MEDIA_BOX, rect(0, 0, 222, 333));
                attach(mid, page("midwins"));
                return root;
            }
            case "I05": {
                // No MediaBox anywhere -> US Letter default.
                attach(root, page("letter"));
                return root;
            }
            case "I06": {
                // CropBox inherited from root, MediaBox on leaf (clip applies).
                setBox(root, COSName.CROP_BOX, rect(-50, -50, 999, 999));
                COSDictionary leaf = page("cropclip");
                setBox(leaf, COSName.MEDIA_BOX, rect(0, 0, 300, 400));
                attach(root, leaf);
                return root;
            }
            case "I07": {
                // Resources only on an ancestor; leaf inherits "present".
                root.setItem(COSName.RESOURCES, new COSDictionary());
                attach(root, page("resinh"));
                return root;
            }
            case "I08": {
                // /Kids as a direct dict (single page) rather than an array.
                COSDictionary leaf = page("directkid");
                setBox(leaf, COSName.MEDIA_BOX, rect(0, 0, 11, 22));
                leaf.setItem(COSName.PARENT, root);
                root.setItem(COSName.KIDS, leaf);
                root.setInt(COSName.COUNT, 1);
                return root;
            }
            case "I09": {
                // Lying /Count (says 5) with one real page.
                root.setInt(COSName.COUNT, 5);
                setBox(root, COSName.MEDIA_BOX, rect(0, 0, 1, 2));
                attach(root, page("lie"));
                return root;
            }
            case "I10": {
                // Self-referential root /Kids (cycle) plus one page.
                root.setInt(COSName.COUNT, 1);
                setBox(root, COSName.MEDIA_BOX, rect(0, 0, 7, 8));
                kids(root).add(root);
                attach(root, page("aftercycle"));
                return root;
            }
            case "I11": {
                // Node points back at ancestor (mutual cycle).
                root.setInt(COSName.COUNT, 1);
                COSDictionary mid = attach(root, pages(1));
                kids(mid).add(root);
                attach(mid, page("cyc"));
                return root;
            }
            case "I12": {
                // /Kids holds a non-page/non-pages dict (no /Type, has /Font).
                COSDictionary junk = new COSDictionary();
                junk.setItem(COSName.FONT, new COSDictionary());
                junk.setItem(COSName.PARENT, root);
                kids(root).add(junk);
                attach(root, page("afterjunk"));
                root.setInt(COSName.COUNT, 1);
                return root;
            }
            case "I13": {
                // Missing /Type on intermediate; /Kids heuristic keeps it.
                root.removeItem(COSName.TYPE);
                setBox(root, COSName.MEDIA_BOX, rect(0, 0, 9, 9));
                attach(root, page("notype"));
                return root;
            }
            case "I14": {
                // Rotate set high in tree, overridden to 0 at leaf.
                root.setInt(COSName.ROTATE, 90);
                COSDictionary leaf = page("rot0");
                leaf.setInt(COSName.ROTATE, 0);
                attach(root, leaf);
                return root;
            }
            case "I15": {
                // Inheritance must stop at a non-/Pages parent: leaf's parent
                // is a /Page dict carrying MediaBox -> not inherited.
                COSDictionary fakeParent = page("fakeparent");
                setBox(fakeParent, COSName.MEDIA_BOX, rect(0, 0, 500, 500));
                COSDictionary leaf = page("blocked");
                leaf.setItem(COSName.PARENT, fakeParent);
                kids(root).add(leaf);
                root.setInt(COSName.COUNT, 1);
                return root;
            }
            case "I16": {
                // Three pages, MediaBox differs per level: root sets default,
                // middle group overrides, one leaf overrides again.
                root.setInt(COSName.COUNT, 3);
                setBox(root, COSName.MEDIA_BOX, rect(0, 0, 100, 100));
                COSDictionary group = attach(root, pages(2));
                group.setInt(COSName.COUNT, 2);
                setBox(group, COSName.MEDIA_BOX, rect(0, 0, 200, 200));
                attach(group, page("ginh"));
                COSDictionary own = page("gown");
                setBox(own, COSName.MEDIA_BOX, rect(0, 0, 300, 300));
                attach(group, own);
                attach(root, page("rootlevel"));
                return root;
            }
            case "I17": {
                // Rotate inherited, non-multiple-of-90 at leaf -> treated unset
                // so the inherited 90 from root wins? No: leaf carries the
                // attribute (45) which terminates the inheritable walk, then
                // getRotation sees 45 -> returns 0. Tests the interaction.
                root.setInt(COSName.ROTATE, 90);
                COSDictionary leaf = page("rot45");
                leaf.setInt(COSName.ROTATE, 45);
                attach(root, leaf);
                return root;
            }
            case "I18": {
                // CropBox absent everywhere -> defaults to resolved MediaBox.
                setBox(root, COSName.MEDIA_BOX, rect(10, 20, 110, 220));
                attach(root, page("nocrop"));
                return root;
            }
            case "I19": {
                // Empty tree: /Kids present but empty, /Count 0.
                root.setInt(COSName.COUNT, 0);
                return root;
            }
            case "I20": {
                // Null kid in the middle gets repaired to an empty page (US
                // Letter default), then a real page follows.
                root.setInt(COSName.COUNT, 2);
                setBox(root, COSName.MEDIA_BOX, rect(0, 0, 80, 90));
                kids(root).add(COSNull.NULL);
                attach(root, page("after_null"));
                return root;
            }
            default:
                throw new IllegalArgumentException(id);
        }
    }

    /** Format a float so 612.0 -> "612" but 612.5 -> "612.5" (both sides). */
    private static String fmt(float v) {
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
            return Long.toString((long) v);
        }
        return Float.toString(v);
    }

    private static String rectCell(PDRectangle r) {
        return fmt(r.getLowerLeftX()) + "," + fmt(r.getLowerLeftY()) + ","
                + fmt(r.getUpperRightX()) + "," + fmt(r.getUpperRightY());
    }

    private static String pageCell(PDPage page) {
        COSDictionary dict = page.getCOSObject();
        String pid = dict.getString(PROBE_ID, "-");
        String mb;
        String cb;
        String rot;
        String res;
        try {
            mb = rectCell(page.getMediaBox());
        } catch (Throwable e) {
            mb = errorCell(e);
        }
        try {
            cb = rectCell(page.getCropBox());
        } catch (Throwable e) {
            cb = errorCell(e);
        }
        try {
            rot = Integer.toString(page.getRotation());
        } catch (Throwable e) {
            rot = errorCell(e);
        }
        try {
            PDResources r = page.getResources();
            res = r == null ? "null" : "present";
        } catch (Throwable e) {
            res = errorCell(e);
        }
        return pid + "|mb=" + mb + "|cb=" + cb + "|rot=" + rot + "|res=" + res;
    }

    private static String errorCell(Throwable error) {
        if (error instanceof IndexOutOfBoundsException) {
            return "INDEX";
        }
        if (error instanceof IllegalStateException) {
            return "STATE";
        }
        if (error instanceof StackOverflowError) {
            return "STACK";
        }
        return "ERR:" + error.getClass().getSimpleName();
    }

    private static String iterationCell(PDPageTree tree) {
        try {
            List<String> cells = new ArrayList<>();
            for (PDPage page : tree) {
                cells.add(pageCell(page));
            }
            return cells.isEmpty() ? "-" : String.join(";", cells);
        } catch (Throwable error) {
            return errorCell(error);
        }
    }

    private static String getCell(PDPageTree tree, int index) {
        try {
            return pageCell(tree.get(index));
        } catch (Throwable error) {
            return errorCell(error);
        }
    }

    private static void emit(PrintStream out, String id) {
        COSDictionary root = build(id);
        PDPageTree tree = new PDPageTree(root);
        StringBuilder gets = new StringBuilder();
        for (int i = 0; i < GET_SWEEP; i++) {
            if (i > 0) {
                gets.append(',');
            }
            gets.append(getCell(tree, i));
        }
        out.println("CASE " + id
                + " count=" + tree.getCount()
                + " iter=" + iterationCell(tree)
                + " get=" + gets);
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        for (int i = 1; i <= 20; i++) {
            emit(out, String.format("I%02d", i));
        }
    }
}
