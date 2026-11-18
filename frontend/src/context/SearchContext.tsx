import React, { createContext, useContext, useState } from 'react';

export interface SearchScope {
  folderId: string | null;
  folderName: string | null;
}

interface SearchContextType {
  scope: SearchScope;
  setSearchScope: (scope: SearchScope) => void;
  clearSearchScope: () => void;
}

const SearchContext = createContext<SearchContextType | undefined>(undefined);

export const SearchProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [scope, setScope] = useState<SearchScope>({ folderId: null, folderName: null });

  const setSearchScope = (newScope: SearchScope) => {
    setScope(newScope);
  };

  const clearSearchScope = () => {
    setScope({ folderId: null, folderName: null });
  };

  return (
    <SearchContext.Provider value={{ scope, setSearchScope, clearSearchScope }}>
      {children}
    </SearchContext.Provider>
  );
};

export const useSearchScope = () => {
  const context = useContext(SearchContext);
  if (!context) {
    return {
      scope: { folderId: null, folderName: null },
      setSearchScope: () => {},
      clearSearchScope: () => {},
    };
  }
  return context;
};
