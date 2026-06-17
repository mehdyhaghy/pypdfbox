import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;

import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.multipdf.PDFCloneUtility;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Confirms PDFBox 3.0.7 PDFCloneUtility StackOverflows on an indirect cycle
 * that loops back to an *array* ancestor (cloneCOSArray does not pre-register
 * the in-progress clone). The cloner constructor is protected, so it is built
 * via reflection. Prints "overflow" when the SOE fires, "no_overflow:<class>"
 * otherwise.
 */
public class CloneArrayCycleOverflowProbe
{
    public static void main(String[] args) throws Exception
    {
        try (PDDocument dst = new PDDocument())
        {
            Constructor<PDFCloneUtility> ctor =
                    PDFCloneUtility.class.getDeclaredConstructor(PDDocument.class);
            ctor.setAccessible(true);
            PDFCloneUtility cloner = ctor.newInstance(dst);
            Method clone =
                    PDFCloneUtility.class.getMethod("cloneForNewDocument", COSBase.class);

            COSArray a = new COSArray();
            COSArray b = new COSArray();
            a.add(COSInteger.get(1));
            a.add(b);
            COSObject refToA = new COSObject(a);
            b.add(refToA);
            try
            {
                Object cloned = clone.invoke(cloner, a);
                System.out.println("no_overflow:" + cloned.getClass().getSimpleName());
            }
            catch (InvocationTargetException e)
            {
                if (e.getCause() instanceof StackOverflowError)
                {
                    System.out.println("overflow");
                }
                else
                {
                    throw e;
                }
            }
            catch (StackOverflowError e)
            {
                System.out.println("overflow");
            }
        }
    }
}
