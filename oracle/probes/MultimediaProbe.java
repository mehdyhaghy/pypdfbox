import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.filespecification.PDFileSpecification;
import org.apache.pdfbox.pdmodel.interactive.action.PDAction;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionFactory;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionMovie;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionSound;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationSound;

/**
 * Live oracle probe for multimedia + 3D + rendition annotations/actions.
 *
 * Emits a canonical, line-oriented dump of every multimedia property the
 * pinned PDFBox 3.0.7 app jar exposes. Note the app jar is a trimmed
 * distribution: PDAnnotationMovie / PDAnnotationScreen / PDAnnotation3D /
 * PDActionRendition / PDMovie / PDRendition are NOT compiled into it, so the
 * probe falls back to raw COS reads for the fields those wrappers would
 * surface (subtype dispatch + field bytes are version-agnostic), and uses the
 * typed wrappers only where the jar ships them: PDAnnotationSound,
 * PDActionSound, PDActionMovie (thin), PDActionFactory, PDFileSpecification.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> MultimediaProbe input.pdf
 */
public final class MultimediaProbe {
    static final COSName SUBTYPE = COSName.getPDFName("Subtype");
    static final COSName A = COSName.getPDFName("A");
    static final COSName MK = COSName.getPDFName("MK");
    static final COSName S = COSName.getPDFName("S");
    static final COSName MOVIE = COSName.getPDFName("Movie");
    static final COSName F = COSName.getPDFName("F");
    static final COSName SHOW_CONTROLS = COSName.getPDFName("ShowControls");
    static final COSName SOUND = COSName.getPDFName("Sound");
    static final COSName NAME = COSName.getPDFName("Name");
    static final COSName AN = COSName.getPDFName("AN");
    static final COSName OP = COSName.getPDFName("OP");
    static final COSName R = COSName.getPDFName("R");
    static final COSName N = COSName.getPDFName("N");
    static final COSName C = COSName.getPDFName("C");
    static final COSName D = COSName.getPDFName("D");

    static String nz(String v) {
        return v == null ? "NULL" : v;
    }

    static String b(boolean v) {
        return v ? "true" : "false";
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDPage page = doc.getPage(0);
            List<PDAnnotation> annots = page.getAnnotations();
            out.println("annotCount=" + annots.size());
            int idx = 0;
            for (PDAnnotation annot : annots) {
                String prefix = "annot[" + idx + "].";
                String subtype = annot.getSubtype();
                out.println(prefix + "subtype=" + nz(subtype));
                COSDictionary d = annot.getCOSObject();

                if ("Screen".equals(subtype)) {
                    dumpScreen(out, prefix, d);
                } else if ("Movie".equals(subtype)) {
                    dumpMovie(out, prefix, d);
                } else if ("Sound".equals(subtype)) {
                    dumpSound(out, prefix, d, annot);
                }
                idx++;
            }
        }
    }

    // Screen annotation: /MK presence + its /A action (a Rendition action).
    static void dumpScreen(PrintStream out, String prefix, COSDictionary d) throws Exception {
        out.println(prefix + "hasMK=" + b(d.getDictionaryObject(MK) instanceof COSDictionary));
        COSBase actBase = d.getDictionaryObject(A);
        if (actBase instanceof COSDictionary) {
            COSDictionary actDict = (COSDictionary) actBase;
            String actSub = actDict.getNameAsString(S);
            out.println(prefix + "action.subtype=" + nz(actSub));
            // PDActionFactory dispatch: Rendition is NOT mapped in 3.0.7 -> null.
            PDAction created = PDActionFactory.createAction(actDict);
            out.println(prefix + "action.factoryClass="
                    + (created == null ? "NULL" : created.getClass().getSimpleName()));
            if ("Rendition".equals(actSub)) {
                dumpRendition(out, prefix + "rendition.", actDict);
            }
        } else {
            out.println(prefix + "action.subtype=NULL");
            out.println(prefix + "action.factoryClass=NULL");
        }
    }

    // Rendition action fields (raw COS — PDActionRendition is not in the app jar).
    static void dumpRendition(PrintStream out, String prefix, COSDictionary actDict) {
        // /OP operation code (sentinel -1 when absent, matching getInt default).
        out.println(prefix + "op=" + actDict.getInt(OP, -1));
        // /AN screen annotation reference presence + its subtype.
        COSBase anBase = actDict.getDictionaryObject(AN);
        boolean hasAN = anBase instanceof COSDictionary;
        out.println(prefix + "hasAN=" + b(hasAN));
        if (hasAN) {
            out.println(prefix + "anSubtype="
                    + nz(((COSDictionary) anBase).getNameAsString(SUBTYPE)));
        } else {
            out.println(prefix + "anSubtype=NULL");
        }
        // /R rendition dictionary: /S subtype + /N name + media clip filename.
        COSBase rBase = actDict.getDictionaryObject(R);
        if (rBase instanceof COSDictionary) {
            COSDictionary rDict = (COSDictionary) rBase;
            out.println(prefix + "rSubtype=" + nz(rDict.getNameAsString(S)));
            out.println(prefix + "rName=" + nz(rDict.getString(N)));
            // media clip /C -> /S /MCD -> /D file specification -> getFile()
            String clipFile = mediaClipFile(rDict);
            out.println(prefix + "clipFile=" + nz(clipFile));
        } else {
            out.println(prefix + "rSubtype=NULL");
            out.println(prefix + "rName=NULL");
            out.println(prefix + "clipFile=NULL");
        }
    }

    // Walk /R -> /C (media clip) -> /D (file spec) and read getFile().
    static String mediaClipFile(COSDictionary rDict) {
        COSBase cBase = rDict.getDictionaryObject(C);
        if (!(cBase instanceof COSDictionary)) {
            return null;
        }
        COSBase dBase = ((COSDictionary) cBase).getDictionaryObject(D);
        if (dBase == null) {
            return null;
        }
        try {
            PDFileSpecification fs = PDFileSpecification.createFS(dBase);
            return fs == null ? null : fs.getFile();
        } catch (Exception e) {
            return null;
        }
    }

    // Movie annotation: /Movie /F filename via PDFileSpecification + /A flags.
    static void dumpMovie(PrintStream out, String prefix, COSDictionary d) throws Exception {
        COSBase movieBase = d.getDictionaryObject(MOVIE);
        if (movieBase instanceof COSDictionary) {
            COSDictionary movieDict = (COSDictionary) movieBase;
            COSBase fBase = movieDict.getDictionaryObject(F);
            String file = null;
            if (fBase != null) {
                try {
                    PDFileSpecification fs = PDFileSpecification.createFS(fBase);
                    file = fs == null ? null : fs.getFile();
                } catch (Exception e) {
                    file = null;
                }
            }
            out.println(prefix + "movieFile=" + nz(file));
        } else {
            out.println(prefix + "movieFile=NULL");
        }
        // /A activation: boolean or dictionary. Read /ShowControls when dict.
        COSBase actBase = d.getDictionaryObject(A);
        if (actBase instanceof COSBoolean) {
            out.println(prefix + "activationKind=boolean");
            out.println(prefix + "activation=" + b(((COSBoolean) actBase).getValue()));
            out.println(prefix + "showControls=NULL");
        } else if (actBase instanceof COSDictionary) {
            COSDictionary actDict = (COSDictionary) actBase;
            out.println(prefix + "activationKind=dictionary");
            out.println(prefix + "activation=DICT");
            COSBase sc = actDict.getDictionaryObject(SHOW_CONTROLS);
            if (sc instanceof COSBoolean) {
                out.println(prefix + "showControls=" + b(((COSBoolean) sc).getValue()));
            } else {
                out.println(prefix + "showControls=NULL");
            }
        } else {
            out.println(prefix + "activationKind=NULL");
            out.println(prefix + "activation=NULL");
            out.println(prefix + "showControls=NULL");
        }
    }

    // Sound annotation: typed PDAnnotationSound is in the jar.
    static void dumpSound(PrintStream out, String prefix, COSDictionary d, PDAnnotation annot) {
        out.println(prefix + "factoryClass=" + annot.getClass().getSimpleName());
        out.println(prefix + "hasSound=" + b(d.getDictionaryObject(SOUND) instanceof COSStream));
        out.println(prefix + "name=" + nz(d.getNameAsString(NAME)));
    }
}
