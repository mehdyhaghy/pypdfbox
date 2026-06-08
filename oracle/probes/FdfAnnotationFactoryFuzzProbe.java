import java.io.PrintStream;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.fdf.FDFAnnotation;

/** Differential fuzz probe for FDFAnnotation.create. */
public final class FdfAnnotationFactoryFuzzProbe {
    private static final String[] NAMES = {
        "Text", "FreeText", "FileAttachment", "Square", "Circle", "Line",
        "Polygon", "PolyLine", "Polyline", "Ink", "Stamp", "Caret",
        "Highlight", "Underline", "StrikeOut", "Squiggly", "Link", "Sound",
        "UnknownSubtype"
    };

    private static void emit(PrintStream out, String name, COSDictionary dictionary) {
        try {
            FDFAnnotation annotation = FDFAnnotation.create(dictionary);
            out.println("CASE " + name + " "
                    + (annotation == null ? "null" : annotation.getClass().getSimpleName()));
        } catch (Throwable error) {
            out.println("CASE " + name + " ERR:" + error.getClass().getSimpleName());
        }
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        for (String name : NAMES) {
            COSDictionary dictionary = new COSDictionary();
            dictionary.setItem(COSName.SUBTYPE, COSName.getPDFName(name));
            emit(out, name, dictionary);
        }

        emit(out, "missing", new COSDictionary());

        COSDictionary stringSubtype = new COSDictionary();
        stringSubtype.setItem(COSName.SUBTYPE, new COSString("Text"));
        emit(out, "string", stringSubtype);

        COSDictionary integerSubtype = new COSDictionary();
        integerSubtype.setItem(COSName.SUBTYPE, COSInteger.ONE);
        emit(out, "integer", integerSubtype);

        COSDictionary nullSubtype = new COSDictionary();
        nullSubtype.setItem(COSName.SUBTYPE, COSNull.NULL);
        emit(out, "null_value", nullSubtype);
    }
}
