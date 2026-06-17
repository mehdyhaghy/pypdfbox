import java.io.PrintStream;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.interactive.action.PDTargetDirectory;

/**
 * Live oracle probe for {@code PDTargetDirectory} (the {@code /T} target chain
 * of an embedded-GoTo action). No dedicated oracle coverage existed.
 *
 * The behaviourally-load-bearing question is what the INTEGER getters
 * ({@code getPageNumber()} / {@code getAnnotationIndex()}) return on an empty
 * dictionary and — crucially — when {@code /P} / {@code /A} hold the alternate
 * STRING form (a named destination / annotation /NM name). Upstream uses
 * {@code COSDictionary.getInt}, which returns its -1 default for any
 * non-integer value, so the integer getter is NOT null-typed; it silently
 * returns -1. pypdfbox's typed accessors return {@code None} in those cases —
 * this probe pins the upstream contract so the divergence (if any) is precise.
 *
 * No arguments. Output (UTF-8, LF-terminated "key=value" lines).
 */
public final class TargetDirectoryProbe {

    private static String nz(Object v) {
        return v == null ? "NULL" : v.toString();
    }

    public static void main(String[] args) {
        PrintStream out = new PrintStream(System.out, true, java.nio.charset.StandardCharsets.UTF_8);

        PDTargetDirectory e = new PDTargetDirectory();
        out.println("empty.relationship=" + nz(e.getRelationship()));
        out.println("empty.filename=" + nz(e.getFilename()));
        out.println("empty.pageNumber=" + e.getPageNumber());
        out.println("empty.namedDestination=" + nz(e.getNamedDestination()));
        out.println("empty.annotationIndex=" + e.getAnnotationIndex());
        out.println("empty.annotationName=" + nz(e.getAnnotationName()));
        out.println("empty.targetDirectory=" + (e.getTargetDirectory() == null ? "NULL" : "present"));

        // Integer forms.
        PDTargetDirectory p = new PDTargetDirectory();
        p.setRelationship(COSName.getPDFName("P"));
        p.setFilename("inner.pdf");
        p.setPageNumber(3);
        p.setAnnotationIndex(2);
        out.println("int.relationship=" + nz(p.getRelationship()));
        out.println("int.filename=" + nz(p.getFilename()));
        out.println("int.pageNumber=" + p.getPageNumber());
        out.println("int.annotationIndex=" + p.getAnnotationIndex());

        // String form: /P as named destination, /A as annotation name.
        PDTargetDirectory s = new PDTargetDirectory();
        s.getCOSObject().setString(COSName.P, "MyDest");
        s.getCOSObject().setString(COSName.A, "AnnotNM");
        out.println("str.pageNumber=" + s.getPageNumber());
        out.println("str.namedDestination=" + nz(s.getNamedDestination()));
        out.println("str.annotationIndex=" + s.getAnnotationIndex());
        out.println("str.annotationName=" + nz(s.getAnnotationName()));

        // Chained target.
        PDTargetDirectory parent = new PDTargetDirectory();
        PDTargetDirectory child = new PDTargetDirectory();
        child.setFilename("deep.pdf");
        parent.setTargetDirectory(child);
        out.println("chain.target=" + (parent.getTargetDirectory() == null ? "NULL" : "present"));
        out.println("chain.target.filename=" + nz(parent.getTargetDirectory().getFilename()));

        java.util.TreeSet<String> keys = new java.util.TreeSet<>();
        for (COSName k : p.getCOSObject().keySet()) {
            keys.add(k.getName());
        }
        out.println("wire.keys=" + String.join(",", keys));
    }
}
