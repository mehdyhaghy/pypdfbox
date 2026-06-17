import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDDocumentOutline;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineItem;

/**
 * Differential fuzz probe for the document-outline bookmark tree
 * (PDDocumentOutline + PDOutlineItem + PDOutlineNode).
 *
 * <p>Each case hand-builds a malformed/edge outline tree directly out of COS
 * objects (no PDF I/O), wraps the root in a {@link PDDocumentOutline}, and
 * projects two surfaces:
 *
 * <ol>
 *   <li><b>tree</b> — walk the root's {@code children()} iterator and report:
 *       the number of children actually yielded (the recursion-guard result on
 *       cyclic /Next chains), the root's getOpenCount(), and a per-child
 *       projection of title / has-dest / has-action / text-style flags /
 *       has-text-color / count / open.</li>
 *   <li><b>node</b> — for a single hand-built item dictionary, project the
 *       pointer accessors (first/last/next/prev child titles) plus has_children
 *       and the signed open count, exercising broken /First-without-/Last and
 *       /Parent-mismatch shapes.</li>
 * </ol>
 *
 * <p>Output: one {@code CASE <name> ...} line per case (UTF-8). The Python
 * test rebuilds the identical dictionaries with pypdfbox COS objects and diffs
 * the projected line byte-for-byte.
 *
 * <p>Usage: {@code java -cp <pdfbox-app.jar>:<build> OutlineFuzzProbe <surface>}
 * where surface is {@code tree} or {@code node}.
 */
public final class OutlineFuzzProbe {

    private static final COSName TITLE = COSName.getPDFName("Title");
    private static final COSName FIRST = COSName.getPDFName("First");
    private static final COSName LAST = COSName.getPDFName("Last");
    private static final COSName NEXT = COSName.getPDFName("Next");
    private static final COSName PREV = COSName.getPDFName("Prev");

    private static COSDictionary item(String title) {
        COSDictionary d = new COSDictionary();
        if (title != null) {
            d.setItem(TITLE, new COSString(title));
        }
        return d;
    }

    private static COSArray destFit() {
        COSArray a = new COSArray();
        a.add(COSInteger.ZERO);
        a.add(COSName.getPDFName("Fit"));
        return a;
    }

    private static COSDictionary goToAction() {
        COSDictionary a = new COSDictionary();
        a.setItem(COSName.S, COSName.getPDFName("GoTo"));
        a.setItem(COSName.D, destFit());
        return a;
    }

    private static COSArray colorTriple(float r, float g, float b) {
        COSArray a = new COSArray();
        a.add(new COSFloat(r));
        a.add(new COSFloat(g));
        a.add(new COSFloat(b));
        return a;
    }

    // ----- tree surface: a root whose children chain is malformed -----

    /** Build a root /Outlines dict for the named tree case. */
    private static COSDictionary treeRoot(String name) {
        COSDictionary root = new COSDictionary();
        root.setItem(COSName.TYPE, COSName.getPDFName("Outlines"));
        switch (name) {
            case "empty":
                break;
            case "linear3": {
                COSDictionary a = item("A");
                COSDictionary b = item("B");
                COSDictionary c = item("C");
                a.setItem(NEXT, b);
                b.setItem(PREV, a);
                b.setItem(NEXT, c);
                c.setItem(PREV, b);
                root.setItem(FIRST, a);
                root.setItem(LAST, c);
                root.setItem(COSName.COUNT, COSInteger.get(3));
                break;
            }
            case "cycle_next": {
                // A -> B -> A : cyclic /Next chain (recursion guard).
                COSDictionary a = item("A");
                COSDictionary b = item("B");
                a.setItem(NEXT, b);
                b.setItem(PREV, a);
                b.setItem(NEXT, a);
                a.setItem(PREV, b);
                root.setItem(FIRST, a);
                root.setItem(LAST, b);
                break;
            }
            case "self_cycle": {
                // A -> A : item points /Next at itself.
                COSDictionary a = item("A");
                a.setItem(NEXT, a);
                root.setItem(FIRST, a);
                root.setItem(LAST, a);
                break;
            }
            case "first_without_last": {
                COSDictionary a = item("A");
                COSDictionary b = item("B");
                a.setItem(NEXT, b);
                b.setItem(PREV, a);
                root.setItem(FIRST, a);
                // /Last deliberately omitted.
                break;
            }
            case "broken_prev": {
                // sibling chain with a missing /Prev on the middle node.
                COSDictionary a = item("A");
                COSDictionary b = item("B");
                COSDictionary c = item("C");
                a.setItem(NEXT, b);
                b.setItem(NEXT, c);
                c.setItem(PREV, b);
                root.setItem(FIRST, a);
                root.setItem(LAST, c);
                break;
            }
            case "title_variants": {
                COSDictionary str = item("Str");
                COSDictionary nm = new COSDictionary();
                nm.setItem(TITLE, COSName.getPDFName("NameTitle"));
                COSDictionary miss = new COSDictionary();
                str.setItem(NEXT, nm);
                nm.setItem(NEXT, miss);
                root.setItem(FIRST, str);
                root.setItem(LAST, miss);
                break;
            }
            case "dest_and_action": {
                COSDictionary both = item("Both");
                both.setItem(COSName.DEST, destFit());
                both.setItem(COSName.A, goToAction());
                COSDictionary destOnly = item("DestOnly");
                destOnly.setItem(COSName.DEST, destFit());
                COSDictionary actOnly = item("ActOnly");
                actOnly.setItem(COSName.A, goToAction());
                both.setItem(NEXT, destOnly);
                destOnly.setItem(NEXT, actOnly);
                root.setItem(FIRST, both);
                root.setItem(LAST, actOnly);
                break;
            }
            case "action_wrong_type": {
                COSDictionary a = item("A");
                a.setItem(COSName.A, COSInteger.ONE);
                root.setItem(FIRST, a);
                root.setItem(LAST, a);
                break;
            }
            case "color_variants": {
                COSDictionary good = item("Good");
                good.setItem(COSName.C, colorTriple(1f, 0f, 0f));
                COSDictionary shortArr = item("Short");
                COSArray two = new COSArray();
                two.add(new COSFloat(0.5f));
                two.add(new COSFloat(0.5f));
                shortArr.setItem(COSName.C, two);
                COSDictionary badElem = item("BadElem");
                COSArray bad = new COSArray();
                bad.add(new COSFloat(0.25f));
                bad.add(COSName.getPDFName("X"));
                bad.add(new COSFloat(0.75f));
                badElem.setItem(COSName.C, bad);
                COSDictionary notArr = item("NotArr");
                notArr.setItem(COSName.C, COSInteger.ONE);
                good.setItem(NEXT, shortArr);
                shortArr.setItem(NEXT, badElem);
                badElem.setItem(NEXT, notArr);
                root.setItem(FIRST, good);
                root.setItem(LAST, notArr);
                break;
            }
            case "flag_variants": {
                COSDictionary italic = item("Italic");
                italic.setItem(COSName.F, COSInteger.get(1));
                COSDictionary bold = item("Bold");
                bold.setItem(COSName.F, COSInteger.get(2));
                COSDictionary both = item("BoldItalic");
                both.setItem(COSName.F, COSInteger.get(3));
                COSDictionary floatFlag = item("Float");
                floatFlag.setItem(COSName.F, new COSFloat(1.0f));
                COSDictionary strFlag = item("Str");
                strFlag.setItem(COSName.F, new COSString("1"));
                italic.setItem(NEXT, bold);
                bold.setItem(NEXT, both);
                both.setItem(NEXT, floatFlag);
                floatFlag.setItem(NEXT, strFlag);
                root.setItem(FIRST, italic);
                root.setItem(LAST, strFlag);
                break;
            }
            case "count_open": {
                COSDictionary a = item("Open");
                a.setItem(COSName.COUNT, COSInteger.get(2));
                COSDictionary b = item("Closed");
                b.setItem(COSName.COUNT, COSInteger.get(-2));
                COSDictionary c = item("Zero");
                c.setItem(COSName.COUNT, COSInteger.ZERO);
                COSDictionary e = item("NoCount");
                a.setItem(NEXT, b);
                b.setItem(NEXT, c);
                c.setItem(NEXT, e);
                root.setItem(FIRST, a);
                root.setItem(LAST, e);
                break;
            }
            case "root_count_negative": {
                // root /Count negative — PDDocumentOutline.isNodeOpen is
                // hard-coded true regardless.
                COSDictionary a = item("A");
                root.setItem(FIRST, a);
                root.setItem(LAST, a);
                root.setItem(COSName.COUNT, COSInteger.get(-1));
                break;
            }
            case "nested_children": {
                COSDictionary parent = item("Parent");
                parent.setItem(COSName.COUNT, COSInteger.get(2));
                COSDictionary kid1 = item("Kid1");
                COSDictionary kid2 = item("Kid2");
                kid1.setItem(COSName.PARENT, parent);
                kid2.setItem(COSName.PARENT, parent);
                kid1.setItem(NEXT, kid2);
                kid2.setItem(PREV, kid1);
                parent.setItem(FIRST, kid1);
                parent.setItem(LAST, kid2);
                parent.setItem(COSName.PARENT, root);
                root.setItem(FIRST, parent);
                root.setItem(LAST, parent);
                break;
            }
            default:
                throw new IllegalArgumentException("unknown tree case: " + name);
        }
        return root;
    }

    private static String j(String s) {
        if (s == null) {
            return "null";
        }
        return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }

    private static String colorCell(PDOutlineItem it) {
        try {
            org.apache.pdfbox.pdmodel.graphics.color.PDColor c = it.getTextColor();
            if (c == null) {
                return "null";
            }
            float[] comps = c.getComponents();
            StringBuilder sb = new StringBuilder("[");
            for (int i = 0; i < comps.length; i++) {
                if (i > 0) {
                    sb.append(",");
                }
                sb.append(fmt(comps[i]));
            }
            sb.append("]");
            return sb.toString();
        } catch (Throwable err) {
            return "ERR:" + err.getClass().getSimpleName();
        }
    }

    private static String fmt(float f) {
        if (f == Math.rint(f) && !Float.isInfinite(f)) {
            return Integer.toString((int) f);
        }
        return Float.toString(f);
    }

    private static String childCell(PDOutlineItem it) {
        StringBuilder sb = new StringBuilder();
        String dest;
        try {
            dest = Boolean.toString(it.getDestination() != null);
        } catch (Throwable err) {
            dest = "ERR:" + err.getClass().getSimpleName();
        }
        sb.append("title=").append(j(it.getTitle()));
        sb.append(" dest=").append(dest);
        sb.append(" act=").append(it.getAction() != null);
        sb.append(" italic=").append(it.isItalic());
        sb.append(" bold=").append(it.isBold());
        sb.append(" count=").append(it.getOpenCount());
        sb.append(" color=").append(colorCell(it));
        return sb.toString();
    }

    private static void treeSurface(PrintStream out, String name) {
        COSDictionary root = treeRoot(name);
        PDDocumentOutline outline = new PDDocumentOutline(root);
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name);
        sb.append(" root_open=").append(outline.isNodeOpen());
        sb.append(" root_count=").append(outline.getOpenCount());
        sb.append(" has_children=").append(outline.hasChildren());
        int n = 0;
        StringBuilder kids = new StringBuilder();
        try {
            for (PDOutlineItem child : outline.children()) {
                kids.append(" [").append(childCell(child)).append("]");
                n++;
                if (n > 50) {
                    kids.append(" [RUNAWAY]");
                    break;
                }
            }
            sb.append(" yielded=").append(n);
            sb.append(kids);
        } catch (Throwable err) {
            sb.append(" yielded=ERR:").append(err.getClass().getSimpleName());
        }
        out.println(sb.toString());
    }

    // ----- node surface: pointer accessors over malformed single items -----

    private static COSDictionary nodeDict(String name) {
        COSDictionary d = item("Self");
        switch (name) {
            case "bare":
                break;
            case "first_only": {
                COSDictionary c = item("OnlyChild");
                c.setItem(COSName.PARENT, d);
                d.setItem(FIRST, c);
                // /Last omitted.
                break;
            }
            case "last_only": {
                COSDictionary c = item("OnlyChild");
                c.setItem(COSName.PARENT, d);
                d.setItem(LAST, c);
                break;
            }
            case "first_last_same": {
                COSDictionary c = item("OnlyChild");
                c.setItem(COSName.PARENT, d);
                d.setItem(FIRST, c);
                d.setItem(LAST, c);
                d.setItem(COSName.COUNT, COSInteger.ONE);
                break;
            }
            case "first_wrong_type":
                d.setItem(FIRST, COSInteger.ONE);
                break;
            case "next_prev": {
                COSDictionary nx = item("Next");
                COSDictionary pv = item("Prev");
                d.setItem(NEXT, nx);
                d.setItem(PREV, pv);
                break;
            }
            case "count_negative":
                d.setItem(COSName.COUNT, COSInteger.get(-3));
                break;
            case "count_positive":
                d.setItem(COSName.COUNT, COSInteger.get(3));
                break;
            default:
                throw new IllegalArgumentException("unknown node case: " + name);
        }
        return d;
    }

    private static String titleOf(PDOutlineItem it) {
        return it == null ? "null" : (it.getTitle() == null ? "null" : it.getTitle());
    }

    private static void nodeSurface(PrintStream out, String name) {
        PDOutlineItem it = new PDOutlineItem(nodeDict(name));
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name);
        sb.append(" has_children=").append(it.hasChildren());
        sb.append(" open_count=").append(it.getOpenCount());
        sb.append(" is_open=").append(it.isNodeOpen());
        sb.append(" first=").append(titleOf(it.getFirstChild()));
        sb.append(" last=").append(titleOf(it.getLastChild()));
        sb.append(" next=").append(titleOf(it.getNextSibling()));
        sb.append(" prev=").append(titleOf(it.getPreviousSibling()));
        sb.append(" collapsed=").append(it.getOpenCount() < 0);
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String surface = args[0];
        String[] treeCases = {"empty", "linear3", "cycle_next", "self_cycle",
            "first_without_last", "broken_prev", "title_variants",
            "dest_and_action", "action_wrong_type", "color_variants",
            "flag_variants", "count_open", "root_count_negative",
            "nested_children"};
        String[] nodeCases = {"bare", "first_only", "last_only",
            "first_last_same", "first_wrong_type", "next_prev",
            "count_negative", "count_positive"};
        if ("tree".equals(surface)) {
            if (args.length > 1) {
                treeSurface(out, args[1]);
            } else {
                for (String c : treeCases) {
                    treeSurface(out, c);
                }
            }
        } else if ("node".equals(surface)) {
            if (args.length > 1) {
                nodeSurface(out, args[1]);
            } else {
                for (String c : nodeCases) {
                    nodeSurface(out, c);
                }
            }
        } else {
            throw new IllegalArgumentException("unknown surface: " + surface);
        }
    }
}
