import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;
import org.apache.pdfbox.pdmodel.interactive.form.PDTextField;

/**
 * Live oracle probe for the AcroForm FIELD FLAG + METADATA accessor surface.
 *
 * For each named field, emit a canonical, deterministic, LF-terminated line
 * carrying the raw /Ff int and every /Ff bit predicate plus the metadata
 * accessors (/MaxLen, /TU, /TM, /Q), so pypdfbox can be diffed against
 * Apache PDFBox's actual behaviour.
 *
 * Usage: java FieldFlagsProbe in.pdf name [name ...]
 *
 * Output (UTF-8) — one line per name:
 *
 *   <name>\tff=<int>\tmultiline=<0/1>\tpassword=<0/1>\tcomb=<0/1>
 *     \tdoNotScroll=<0/1>\tdoNotSpellCheck=<0/1>\tfileSelect=<0/1>
 *     \treadOnly=<0/1>\trequired=<0/1>\tnoExport=<0/1>
 *     \tmaxLen=<int>\ttu=<str|none>\ttm=<str|none>\tq=<int>
 *
 * The /Ff-bit predicates (isMultiline / isPassword / isComb /
 * doNotScroll / doNotSpellCheck / isFileSelect on PDTextField, and
 * isReadOnly / isRequired / isNoExport on PDField) are the high-value
 * matrix: each maps to a single /Ff bit, so a one-bit mistake flips a
 * predicate. A missing field emits "<missing>".
 */
public final class FieldFlagsProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDAcroForm form = doc.getDocumentCatalog().getAcroForm();
            StringBuilder sb = new StringBuilder();
            for (int i = 1; i < args.length; i++) {
                String name = args[i];
                PDField field = form == null ? null : form.getField(name);
                if (field == null) {
                    sb.append(name).append("\t<missing>\n");
                    continue;
                }
                sb.append(line(name, field)).append('\n');
            }
            out.print(sb);
        }
    }

    private static String line(String name, PDField field) {
        int ff = field.getCOSObject().getInt("Ff", 0);
        boolean multiline = false;
        boolean password = false;
        boolean comb = false;
        boolean doNotScroll = false;
        boolean doNotSpellCheck = false;
        boolean fileSelect = false;
        int maxLen = -1;
        int q = 0;
        if (field instanceof PDTextField) {
            PDTextField tf = (PDTextField) field;
            multiline = tf.isMultiline();
            password = tf.isPassword();
            comb = tf.isComb();
            doNotScroll = tf.doNotScroll();
            doNotSpellCheck = tf.doNotSpellCheck();
            fileSelect = tf.isFileSelect();
            maxLen = tf.getMaxLen();
            q = tf.getQ();
        }
        return name
                + "\tff=" + ff
                + "\tmultiline=" + b(multiline)
                + "\tpassword=" + b(password)
                + "\tcomb=" + b(comb)
                + "\tdoNotScroll=" + b(doNotScroll)
                + "\tdoNotSpellCheck=" + b(doNotSpellCheck)
                + "\tfileSelect=" + b(fileSelect)
                + "\treadOnly=" + b(field.isReadOnly())
                + "\trequired=" + b(field.isRequired())
                + "\tnoExport=" + b(field.isNoExport())
                + "\tmaxLen=" + maxLen
                + "\ttu=" + esc(field.getAlternateFieldName())
                + "\ttm=" + esc(field.getMappingName())
                + "\tq=" + q;
    }

    private static String b(boolean v) {
        return v ? "1" : "0";
    }

    private static String esc(String s) {
        if (s == null) {
            return "none";
        }
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")
                .replace("\t", "\\t");
    }
}
