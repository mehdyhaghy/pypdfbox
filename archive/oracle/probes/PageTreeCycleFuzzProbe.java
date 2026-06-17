import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageTree;

/** Differential fuzz probe for malformed PDPageTree traversal and lookup. */
public final class PageTreeCycleFuzzProbe {
    private static final COSName PROBE_ID = COSName.getPDFName("ProbeID");
    private static final COSName INHERITED = COSName.getPDFName("ProbeInherited");

    private static final class CaseData {
        private final COSDictionary root;
        private final COSDictionary inheritedNode;

        private CaseData(COSDictionary root, COSDictionary inheritedNode) {
            this.root = root;
            this.inheritedNode = inheritedNode;
        }
    }

    private static COSDictionary root(int count) {
        COSDictionary root = new COSDictionary();
        root.setItem(COSName.TYPE, COSName.PAGES);
        root.setItem(COSName.KIDS, new COSArray());
        root.setInt(COSName.COUNT, count);
        return root;
    }

    private static COSArray kids(COSDictionary node) {
        return (COSArray) node.getDictionaryObject(COSName.KIDS);
    }

    private static COSDictionary leaf(String id) {
        COSDictionary leaf = new COSDictionary();
        leaf.setItem(COSName.TYPE, COSName.PAGE);
        leaf.setString(PROBE_ID, id);
        return leaf;
    }

    private static COSDictionary branch(int count) {
        return root(count);
    }

    private static CaseData build(String id) {
        COSDictionary root;
        COSDictionary node;
        COSDictionary leaf;
        switch (id) {
            case "P01":
                root = root(2);
                kids(root).add(leaf("a"));
                kids(root).add(leaf("b"));
                return new CaseData(root, null);
            case "P02":
                root = root(1);
                kids(root).add(root);
                return new CaseData(root, null);
            case "P03":
                root = root(1);
                node = branch(1);
                kids(root).add(node);
                kids(node).add(root);
                return new CaseData(root, null);
            case "P04":
                root = root(1);
                root.setItem(COSName.KIDS, COSInteger.ONE);
                return new CaseData(root, null);
            case "P05":
                root = root(1);
                root.removeItem(COSName.KIDS);
                return new CaseData(root, null);
            case "P06":
                root = root(1);
                kids(root).add(COSNull.NULL);
                return new CaseData(root, null);
            case "P07":
                root = root(2);
                kids(root).add(COSInteger.ONE);
                kids(root).add(COSName.getPDFName("BadKid"));
                kids(root).add(COSNull.NULL);
                kids(root).add(leaf("a"));
                return new CaseData(root, null);
            case "P08":
                root = root(1);
                kids(root).add(leaf("a"));
                kids(root).add(leaf("b"));
                return new CaseData(root, null);
            case "P09":
                root = root(3);
                kids(root).add(leaf("a"));
                return new CaseData(root, null);
            case "P10":
                root = root(2);
                leaf = leaf("a");
                kids(root).add(leaf);
                kids(root).add(leaf);
                return new CaseData(root, null);
            case "P11":
                root = root(2);
                node = branch(1);
                kids(node).add(leaf("a"));
                kids(root).add(node);
                kids(root).add(node);
                return new CaseData(root, null);
            case "P12":
                root = root(1);
                node = root;
                for (int i = 0; i < 256; i++) {
                    COSDictionary child = branch(1);
                    kids(node).add(child);
                    node = child;
                }
                kids(node).add(leaf("deep"));
                return new CaseData(root, null);
            case "P13":
                root = root(1);
                leaf = new COSDictionary();
                leaf.setString(PROBE_ID, "missing");
                kids(root).add(leaf);
                return new CaseData(root, null);
            case "P14":
                root = root(1);
                leaf = leaf("wrong");
                leaf.setItem(COSName.TYPE, COSName.getPDFName("Wrong"));
                kids(root).add(leaf);
                return new CaseData(root, null);
            case "P15":
                root = root(1);
                leaf = leaf("integer");
                leaf.setItem(COSName.TYPE, COSInteger.ONE);
                kids(root).add(leaf);
                return new CaseData(root, null);
            case "P16":
                root = root(1);
                leaf = leaf("page-kids");
                leaf.setItem(COSName.KIDS, COSInteger.ONE);
                kids(root).add(leaf);
                return new CaseData(root, null);
            case "P17":
                root = root(1);
                root.removeItem(COSName.TYPE);
                kids(root).add(leaf("a"));
                return new CaseData(root, null);
            case "P18":
                root = root(1);
                leaf = leaf("self-parent");
                leaf.setItem(COSName.PARENT, leaf);
                kids(root).add(leaf);
                return new CaseData(root, leaf);
            case "P19":
                root = root(1);
                leaf = leaf("parent-cycle");
                COSDictionary parentA = branch(0);
                COSDictionary parentB = branch(0);
                leaf.setItem(COSName.PARENT, parentA);
                parentA.setItem(COSName.PARENT, parentB);
                parentB.setItem(COSName.PARENT, parentA);
                kids(root).add(leaf);
                return new CaseData(root, leaf);
            case "P20":
                root = root(1);
                leaf = leaf("blocked-parent");
                node = leaf("not-pages");
                node.setString(INHERITED, "blocked");
                leaf.setItem(COSName.PARENT, node);
                kids(root).add(leaf);
                return new CaseData(root, leaf);
            case "P21":
                root = root(1);
                leaf = leaf("inherited");
                node = branch(0);
                node.setString(INHERITED, "ok");
                leaf.setItem(COSName.PARENT, node);
                kids(root).add(leaf);
                return new CaseData(root, leaf);
            case "P22":
                root = root(2);
                node = branch(0);
                kids(node).add(leaf("hidden"));
                kids(root).add(node);
                kids(root).add(leaf("direct"));
                return new CaseData(root, null);
            case "P23":
                root = root(1);
                node = branch(0);
                node.removeItem(COSName.KIDS);
                kids(root).add(node);
                return new CaseData(root, null);
            default:
                throw new IllegalArgumentException(id);
        }
    }

    private static String pageCell(PDPage page) {
        COSDictionary dictionary = page.getCOSObject();
        String id = dictionary.getString(PROBE_ID, "-");
        String type = dictionary.getNameAsString(COSName.TYPE, "-");
        return id + ":" + type;
    }

    private static String iterationCell(PDPageTree tree) {
        try {
            List<String> pages = new ArrayList<>();
            for (PDPage page : tree) {
                pages.add(pageCell(page));
            }
            return pages.isEmpty() ? "-" : String.join(",", pages);
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

    private static String inheritedCell(COSDictionary node) {
        if (node == null) {
            return "-";
        }
        COSBase value = PDPageTree.getInheritableAttribute(node, INHERITED);
        return value instanceof COSString ? ((COSString) value).getString() : "null";
    }

    private static String firstParentCell(COSDictionary root) {
        COSArray kids = root.getCOSArray(COSName.KIDS);
        if (kids == null || kids.size() == 0) {
            return "-";
        }
        COSBase first = kids.getObject(0);
        if (!(first instanceof COSDictionary)) {
            return "-";
        }
        COSDictionary parent = ((COSDictionary) first).getCOSDictionary(COSName.PARENT);
        if (parent == null) {
            return "null";
        }
        return parent == root ? "root" : "other";
    }

    private static void emit(PrintStream out, String id) {
        CaseData data = build(id);
        PDPageTree tree = new PDPageTree(data.root);
        String iteration = iterationCell(tree);
        out.println("CASE " + id
                + " iter=" + iteration
                + " count=" + tree.getCount()
                + " get0=" + getCell(tree, 0)
                + " get1=" + getCell(tree, 1)
                + " inherit=" + inheritedCell(data.inheritedNode)
                + " firstParent=" + firstParentCell(data.root));
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        for (int i = 1; i <= 23; i++) {
            emit(out, String.format("P%02d", i));
        }
    }
}
