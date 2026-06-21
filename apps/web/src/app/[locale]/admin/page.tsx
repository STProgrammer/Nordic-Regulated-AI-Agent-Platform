import { ProtectedPage } from '@/components/auth/protected-page';
import { ControlledMemoryPanel } from '@/components/admin/controlled-memory-panel';

export default function AdminPage() {
  return (
    <ProtectedPage>
      <ControlledMemoryPanel />
    </ProtectedPage>
  );
}
