interface Project {
    id: string;
    name: string;
    address: string;
    description: string | null;
    budget_total: number | string;
    budget_spent: number | string;
    client_id: string | null;
    created_at: string;
}
interface ProjectWorkspaceProps {
    project: Project;
    onClose: () => void;
}
export declare function ProjectWorkspace({ project, onClose }: ProjectWorkspaceProps): import("react/jsx-runtime").JSX.Element;
export {};
