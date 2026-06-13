import { FileText } from 'lucide-react'

import { getMediaFileName, getMediaUrl, isImageMedia } from './mediaUtils'

type MessageMediaAttachmentProps = {
    mediaUrl?: string | null
    mediaFilename?: string | null
    mediaMimetype?: string | null
    isOutbound: boolean
}

export function MessageMediaAttachment({ mediaUrl, mediaFilename, mediaMimetype, isOutbound }: MessageMediaAttachmentProps) {
    const resolvedUrl = getMediaUrl(mediaUrl)
    if (!resolvedUrl) return null

    if (isImageMedia(resolvedUrl, mediaMimetype)) {
        return (
            <a href={resolvedUrl} target="_blank" rel="noreferrer" className="mb-2 block overflow-hidden rounded-xl">
                <img
                    src={resolvedUrl}
                    alt="Вложение"
                    className="max-h-64 w-full max-w-xs object-cover"
                    loading="lazy"
                />
            </a>
        )
    }

    return (
        <a
            href={resolvedUrl}
            target="_blank"
            rel="noreferrer"
            className={`mb-2 flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold transition-colors ${isOutbound
                    ? 'border-primary-foreground/30 bg-primary-foreground/10 text-primary-foreground hover:bg-primary-foreground/20'
                    : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                }`}
        >
            <FileText className="h-4 w-4 shrink-0" />
            <span className="truncate">{mediaFilename || getMediaFileName(resolvedUrl)}</span>
        </a>
    )
}
