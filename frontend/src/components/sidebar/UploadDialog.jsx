import { Loader2, Upload } from "lucide-react";
import { useState } from "react";

import { cn } from "../../utils/cn";
import Dialog from "../ui/Dialog";

function UploadDialog({ error, open, uploading, onClose, onUpload }) {
  const [dragging, setDragging] = useState(false);

  const upload = async (file) => {
    if (file && !uploading && (await onUpload(file))) {
      onClose();
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Upload a PDF"
      description="The file is indexed so you can ask questions about it. Up to 20 MB."
    >
      <label
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          upload(event.dataTransfer.files?.[0]);
        }}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed px-6 py-10 text-center transition-colors",
          dragging
            ? "border-brand-500 bg-brand-50 dark:bg-brand-500/10"
            : "border-zinc-300 hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-800/50"
        )}
      >
        <input
          type="file"
          accept="application/pdf"
          className="sr-only"
          disabled={uploading}
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            upload(file);
          }}
        />
        {uploading ? (
          <Loader2 className="h-6 w-6 animate-spin text-brand-500" />
        ) : (
          <Upload className="h-6 w-6 text-zinc-400" />
        )}
        <p className="mt-3 text-sm font-medium">
          {uploading ? "Uploading and indexing…" : "Drop a PDF here or click to browse"}
        </p>
      </label>

      {error && (
        <p
          role="alert"
          className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600 dark:bg-red-500/10 dark:text-red-400"
        >
          {error}
        </p>
      )}
    </Dialog>
  );
}

export default UploadDialog;
