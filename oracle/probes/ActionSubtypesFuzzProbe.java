import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionHide;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionSound;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionThread;

/**
 * Live oracle probe for the per-subtype accessor leniency of the remaining
 * PDAction subtypes that DO carry typed accessors in PDFBox 3.0.7 —
 * {@code PDActionHide} ({@code getT} / {@code getH}), {@code PDActionThread}
 * ({@code getD} / {@code getB} / {@code getFile}) and {@code PDActionSound}
 * ({@code getSound} / {@code getVolume} / {@code getSynchronous} /
 * {@code getRepeat} / {@code getMix}).
 *
 * <p>(PDActionMovie has no public accessors in 3.0.7; PDActionRendition and
 * PDActionTransition do not exist in 3.0.7 at all — those are pypdfbox-only
 * extensions and have no oracle counterpart.)
 *
 * <p>The wave-1513 {@code ActionFactoryFuzzProbe} projected the raw-COS shape
 * after factory dispatch; this probe instead drives the subtype's own
 * accessor methods on malformed dicts, so it exercises {@code getCOSStream}
 * (Sound), {@code getFloat}+clamp (Volume), {@code getBoolean} defaults and the
 * {@code PDFileSpecification.createFS} dispatch (Thread /F) that the factory
 * probe never touches.
 *
 * <p>Reads the same on-disk {@code corpus.pdf} both libraries parse, so the
 * accessor contract is directly comparable. Arg: the directory containing
 * {@code corpus.pdf} + {@code manifest.txt} (one case name per line, in the
 * /FuzzActions array order).
 *
 * <p>Output (UTF-8, LF-terminated): one {@code CASE <name> <projection>} line
 * per manifest entry.
 */
public final class ActionSubtypesFuzzProbe {

    private static COSName n(String s) {
        return COSName.getPDFName(s);
    }

    private static String shape(COSBase b) {
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
        if (b instanceof org.apache.pdfbox.cos.COSName) {
            return "name";
        }
        if (b instanceof org.apache.pdfbox.cos.COSString) {
            return "str";
        }
        if (b instanceof org.apache.pdfbox.cos.COSBoolean) {
            return "bool";
        }
        if (b instanceof org.apache.pdfbox.cos.COSInteger) {
            return "int";
        }
        if (b instanceof org.apache.pdfbox.cos.COSFloat) {
            return "real";
        }
        return "other";
    }

    private static String hideLine(COSDictionary d) {
        PDActionHide a = new PDActionHide(d);
        return "t=" + shape(a.getT()) + ",h=" + a.getH();
    }

    private static String threadLine(COSDictionary d) {
        PDActionThread a = new PDActionThread(d);
        String file;
        try {
            Object fs = a.getFile();
            file = fs == null ? "null" : fs.getClass().getSimpleName();
        } catch (Exception ex) {
            file = "ERR:" + ex.getClass().getSimpleName();
        }
        return "d=" + shape(a.getD()) + ",b=" + shape(a.getB()) + ",file=" + file;
    }

    private static String soundLine(COSDictionary d) {
        PDActionSound a = new PDActionSound(d);
        COSStream snd = a.getSound();
        return "sound=" + (snd == null ? "null" : "stream")
                + ",vol=" + a.getVolume()
                + ",sync=" + a.getSynchronous()
                + ",rep=" + a.getRepeat()
                + ",mix=" + a.getMix();
    }

    private static String project(String name, COSDictionary d) {
        if (d == null) {
            return "NODICT";
        }
        if (name.startsWith("hide_")) {
            return hideLine(d);
        }
        if (name.startsWith("thread_")) {
            return threadLine(d);
        }
        if (name.startsWith("sound_")) {
            return soundLine(d);
        }
        return "UNKNOWN";
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, StandardCharsets.UTF_8);
        java.nio.file.Path dir = java.nio.file.Paths.get(args[0]);
        java.util.List<String> order =
                java.nio.file.Files.readAllLines(dir.resolve("manifest.txt"), StandardCharsets.UTF_8);

        try (PDDocument doc = org.apache.pdfbox.Loader.loadPDF(dir.resolve("corpus.pdf").toFile())) {
            COSDictionary catalog = doc.getDocumentCatalog().getCOSObject();
            COSArray arr = (COSArray) catalog.getDictionaryObject(n("FuzzActions"));
            int i = 0;
            for (String name : order) {
                if (name.isEmpty()) {
                    continue;
                }
                COSBase entry = arr.getObject(i++);
                COSDictionary d = entry instanceof COSDictionary ? (COSDictionary) entry : null;
                String proj;
                try {
                    proj = project(name, d);
                } catch (Exception ex) {
                    proj = "ERR:" + ex.getClass().getSimpleName();
                }
                out.println("CASE " + name + " " + proj);
            }
        }
    }
}
