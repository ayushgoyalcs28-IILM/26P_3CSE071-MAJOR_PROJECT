import {describe,expect,it} from 'vitest';
import {formatSize,getFileKind,initials} from './utils';
describe('display helpers',()=>{
 it('formats sizes correctly',()=>{expect(formatSize(0)).toBe('0 B');expect(formatSize(2048)).toBe('2.00 KB');});
 it('detects document categories',()=>{expect(getFileKind('report.PDF','application/pdf')).toBe('pdf');expect(getFileKind('photo.png','image/png')).toBe('image');});
 it('derives initials',()=>expect(initials('Alex Morgan')).toBe('AM'));
});
