import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDButton;
import org.apache.pdfbox.pdmodel.interactive.form.PDCheckBox;

/**
 * Differential probe for {@link PDButton#getValue()} / {@link PDButton#getDefaultValue()}
 * when /V or /DV is a COSString (or missing) rather than a COSName.
 *
 * Upstream only reads an {@code instanceof COSName} token; a COSString /V reads
 * back as the default "Off" and a COSString /DV reads back as "".
 *
 * Output is one labelled line per fact so the Python side can match exactly.
 */
public final class ButtonCosStringValueProbe
{
    public static void main(String[] args) throws Exception
    {
        try (PDDocument doc = new PDDocument())
        {
            PDAcroForm form = new PDAcroForm(doc);

            PDCheckBox cb = new PDCheckBox(form);
            cb.getCOSObject().setString(COSName.V, "string-value");
            cb.getCOSObject().setString(COSName.DV, "default-value");
            System.out.println("value_cosstring=" + cb.getValue());
            System.out.println("default_cosstring=" + cb.getDefaultValue());

            cb.getCOSObject().removeItem(COSName.V);
            System.out.println("value_missing=" + cb.getValue());

            cb.getCOSObject().setName(COSName.V, "Yes");
            System.out.println("value_cosname=" + cb.getValue());
        }
    }
}
