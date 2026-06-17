import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDEmbeddedFilesNameTreeNode;
import org.apache.pdfbox.pdmodel.PDJavascriptNameTreeNode;
import org.apache.pdfbox.pdmodel.common.COSObjectable;

/**
 * Live oracle probe (wave 1532, agent A): pin the per-subclass leaf
 * value-wrapping of the typed {@code PDNameTreeNode} subclasses that EXIST in
 * the PDFBox 3.0.7 jar — {@link PDJavascriptNameTreeNode} (→ PDActionJavaScript)
 * and {@link PDEmbeddedFilesNameTreeNode} (→ PDComplexFileSpecification).
 *
 * <p>{@code PDDestinationNameTreeNode} and {@code PDStructureElementNameTreeNode}
 * also exist upstream but have no pypdfbox sibling in this agent's zone, so they
 * are out of scope here. The remaining pypdfbox subclasses (URLS / IDS / Pages /
 * Templates / Renditions / AlternatePresentations) are pypdfbox-only additions
 * with no upstream class — they are covered by hand-tests, not this oracle.
 *
 * <p>For each subclass the probe drives {@code convertCOSToPD(leaf)} over a
 * battery of malformed / well-formed leaf COS values and prints the resulting
 * wrapped-object's simple class name, or {@code ERR:<ExcSimpleName>} on throw.
 * The {@code convertCOSToPD} method is protected, so a thin local subclass
 * exposes it.
 *
 * <p>Line grammar (one per case): {@code CASE <node> <leaf> -> <result>} where
 * result is {@code <SimpleClassName>} or {@code null} or {@code ERR:<Exc>}.
 */
public final class TypedNameTreeNodeFuzzProbe {

    static final class JsNode extends PDJavascriptNameTreeNode {
        Object call(COSBase b) {
            try {
                COSObjectable v = convertCOSToPD(b);
                return v == null ? "null" : v.getClass().getSimpleName();
            } catch (Throwable t) {
                return "ERR:" + t.getClass().getSimpleName();
            }
        }
    }

    static final class EfNode extends PDEmbeddedFilesNameTreeNode {
        Object call(COSBase b) {
            try {
                COSObjectable v = convertCOSToPD(b);
                return v == null ? "null" : v.getClass().getSimpleName();
            } catch (Throwable t) {
                return "ERR:" + t.getClass().getSimpleName();
            }
        }
    }

    static COSDictionary jsDict(String s, COSName subtype) {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.getPDFName("Action"));
        if (subtype != null) {
            d.setItem(COSName.S, subtype);
        }
        if (s != null) {
            d.setString(COSName.JS, s);
        }
        return d;
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = System.out;
        JsNode js = new JsNode();
        EfNode ef = new EfNode();

        // -- Javascript leaf shapes --
        out.println("CASE js null -> " + js.call(null));
        out.println("CASE js cosstring -> " + js.call(new COSString("app.alert(1)")));
        out.println("CASE js cosname -> " + js.call(COSName.getPDFName("Foo")));
        out.println("CASE js cosint -> " + js.call(COSInteger.get(3)));
        out.println("CASE js cosnull -> " + js.call(COSNull.NULL));
        out.println("CASE js cosarray -> " + js.call(new COSArray()));
        // well-formed JS action dict
        out.println("CASE js dict_js_action -> "
                + js.call(jsDict("app.alert(1)", COSName.JAVA_SCRIPT)));
        // dict with /JS but /S not JavaScript (e.g. URI action)
        out.println("CASE js dict_wrong_S -> "
                + js.call(jsDict("app.alert(1)", COSName.getPDFName("URI"))));
        // dict missing /S entirely
        out.println("CASE js dict_no_S -> " + js.call(jsDict("app.alert(1)", null)));
        // dict missing /JS body
        out.println("CASE js dict_no_JS -> " + js.call(jsDict(null, COSName.JAVA_SCRIPT)));
        // empty dict
        out.println("CASE js dict_empty -> " + js.call(new COSDictionary()));
        // dict with /JS as a stream
        COSDictionary jsStreamDict = new COSDictionary();
        jsStreamDict.setItem(COSName.S, COSName.JAVA_SCRIPT);
        COSStream jsStream = new COSStream();
        jsStream.createOutputStream().write("app.print()".getBytes("UTF-8"));
        jsStreamDict.setItem(COSName.JS, jsStream);
        out.println("CASE js dict_js_stream -> " + js.call(jsStreamDict));

        // -- EmbeddedFiles leaf shapes --
        out.println("CASE ef null -> " + ef.call(null));
        out.println("CASE ef cosnull -> " + ef.call(COSNull.NULL));
        out.println("CASE ef empty_dict -> " + ef.call(new COSDictionary()));
        out.println("CASE ef cosstring -> " + ef.call(new COSString("x")));
        out.println("CASE ef cosname -> " + ef.call(COSName.getPDFName("Foo")));
        out.println("CASE ef cosint -> " + ef.call(COSInteger.get(1)));
        out.println("CASE ef cosarray -> " + ef.call(new COSArray()));
        // well-formed filespec dict
        COSDictionary fs = new COSDictionary();
        fs.setItem(COSName.TYPE, COSName.getPDFName("Filespec"));
        fs.setString(COSName.F, "test.txt");
        out.println("CASE ef filespec_dict -> " + ef.call(fs));
    }
}
