import java.lang.reflect.Constructor;
import java.lang.reflect.Method;

import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.multipdf.PDFCloneUtility;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Probes PDFCloneUtility deep-clone identity semantics. The cloner's
 * constructor is protected, so we build it via reflection (default package).
 * Prints one "key=value" line per observation.
 */
public class CloneSemanticsProbe
{
    static PDFCloneUtility newCloner(PDDocument dst) throws Exception
    {
        Constructor<PDFCloneUtility> ctor =
                PDFCloneUtility.class.getDeclaredConstructor(PDDocument.class);
        ctor.setAccessible(true);
        return ctor.newInstance(dst);
    }

    static COSBase clone(PDFCloneUtility c, COSBase b) throws Exception
    {
        Method m = PDFCloneUtility.class.getMethod("cloneForNewDocument", COSBase.class);
        return (COSBase) m.invoke(c, b);
    }

    public static void main(String[] args) throws Exception
    {
        try (PDDocument dst = new PDDocument())
        {
            PDFCloneUtility cloner = newCloner(dst);

            COSInteger i = COSInteger.get(42);
            System.out.println("int_same=" + (clone(cloner, i) == i));

            COSName n = COSName.getPDFName("Foo");
            System.out.println("name_same=" + (clone(cloner, n) == n));

            COSString s = new COSString("hi");
            System.out.println("string_same=" + (clone(cloner, s) == s));

            System.out.println("null_same=" + (clone(cloner, COSNull.NULL) == COSNull.NULL));

            System.out.println("bool_true_same="
                    + (clone(cloner, COSBoolean.TRUE) == COSBoolean.TRUE));

            System.out.println("javanull=" + (clone(cloner, null) == null));

            COSDictionary d = new COSDictionary();
            d.setItem(COSName.TYPE, COSName.getPDFName("Bar"));
            COSBase c1 = clone(cloner, d);
            COSBase c2 = clone(cloner, d);
            System.out.println("dict_distinct=" + (c1 != d));
            System.out.println("dict_cached_same=" + (c1 == c2));
            System.out.println("dont_clone_clone=" + (clone(cloner, c1) == c1));

            COSArray arr = new COSArray();
            arr.add(COSInteger.get(7));
            arr.add(n);
            COSArray ca = (COSArray) clone(cloner, arr);
            System.out.println("arr_distinct=" + (ca != arr));
            System.out.println("arr_size=" + ca.size());
            System.out.println("arr_name_shared=" + (ca.get(1) == n));

            COSDictionary refd = new COSDictionary();
            refd.setItem(COSName.TYPE, COSName.getPDFName("Ref"));
            COSObject ref = new COSObject(refd);
            COSBase clonedRef = clone(cloner, ref);
            System.out.println("ref_is_dict=" + (clonedRef instanceof COSDictionary));
            System.out.println("ref_not_object=" + !(clonedRef instanceof COSObject));

            COSObject ref2 = new COSObject(refd);
            COSBase clonedRef2 = clone(cloner, ref2);
            System.out.println("shared_target_one_clone=" + (clonedRef == clonedRef2));

            try (PDDocument same = new PDDocument())
            {
                PDFCloneUtility c = newCloner(same);
                COSDictionary sd = same.getDocumentCatalog().getCOSObject();
                COSBase cl = clone(c, sd);
                System.out.println("same_doc_distinct=" + (cl != sd));
                System.out.println("same_doc_is_dict=" + (cl instanceof COSDictionary));
            }
        }
    }
}
